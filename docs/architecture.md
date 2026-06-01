# agent-ls: Architecture & Implementation Plan

## Context

Employees joining teams waste hours deciphering outdated Slack messages and broken setup docs. agent-ls is a local-first CLI/TUI tool that uses LLM-powered agentic workflows to actively set up developer environments on macOS, pulling context from Slack, executing commands with security gates, and maintaining a living knowledge base in Obsidian (Git-synced to the team workspace).

**Key constraints**: macOS-only, local-first, TUI interface, Python/LangGraph, configurable model routing, allowlist-based security.

---

## System Architecture

### Core Data Flow

```
Slack (smart search) → LangGraph (orchestrate + checkpoint) → Obsidian (knowledge store) → Git (team sync) → Team workspace
```

The key insight: **Obsidian + git IS the memory**. LangGraph checkpoints handle cross-run dedup. Failed runs never push. Any team member's last successful commit is a valid "what worked" reference.

### LangGraph State Machine

```
[START] → [CONTEXT_GATHER] → [ROUTER]
                                 │
              ┌──────────────────┼──────────────────────────────┐
              │                  │                              │
              ▼                  ▼                              ▼
     [SMART_SLACK_SEARCH]    [PLAN]                    [KB_FRESHNESS]
              │                  │                              │
              ▼                  ▼                              │
          [EXTRACT]         [EXECUTE LOOP]                     │
              │                  │                              │
              └──────┐           ▼                              │
                     │      [SUMMARIZE]                         │
                     │           │                              │
                     │           ▼                              │
                     └──→  [FINALIZE]  ←───────────────────────┘
                               │
                               ▼
                       [OBSIDIAN_WRITE]
                               │
                               ▼
                        [GIT: commit]
                               │
                     (run_success = true?)
                        /            \
                    yes /              \ no
                       ▼                ▼
                  [GIT: push]       [local only]
                       │
                       ▼
                 [TEAM WORKSPACE]
```

**Additional paths:**
- Share: `ROUTER → OBSIDIAN_READ → SLACK_SHARE → END`
- Search → Execute: `SMART_SLACK_SEARCH → EXTRACT → EXECUTE LOOP → SUMMARIZE → ...`

### Nodes

1. `context_gather` — Pulls user context from Slack profile
2. `router` — Classifies intent: setup, search, share, update_kb (cheap model)
3. `smart_slack_search` — Thread-following, dedup via checkpoint, relevance ranking
4. `extract` — Summarizes Slack results into actionable steps (cheap model)
5. `plan` — Generates step-by-step execution plan (expensive model)
6. `execute` — Runs commands via subprocess with security gate
7. `summarize` — Produces session summary
8. `finalize` — Determines `run_success` (gates git push)
9. `obsidian_write` — Writes to vault, commits, conditionally pushes
10. `kb_freshness` — Checks docs for staleness, falls back to team git history
11. `obsidian_read` / `slack_share` — Read vault docs, post to Slack

### State

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_context: UserContext  # team, role, stack
    intent: str
    plan: list[PlanStep]
    current_step: int
    execution_log: list[ExecutionResult]
    approval_pending: Optional[str]
    obsidian_docs: list[str]
    slack_results: list[SlackMessage]
    error: Optional[str]
    share_channel: Optional[str]
    share_result: Optional[str]
    extracted_urls: list[str]
    processed_message_ids: list[str]  # Cross-run dedup via checkpoint
    run_success: bool                  # Gates git push
```

---

## Smart Slack Search

The Slack bot component provides intelligent search beyond raw `search.messages` API calls:

- **Thread-following**: For each top-level result, fetches thread replies for full context
- **Cross-run dedup**: Uses LangGraph checkpoint state (`processed_message_ids`) to skip already-ingested messages
- **Relevance ranking**: TF-IDF keyword overlap scoring with recency as tiebreaker
- **Configurable depth**: `follow_threads`, `semantic_threshold` in settings

```python
class SmartSearch:
    async def search(
        self,
        query: str,
        channels: list[str] | None = None,
        max_results: int = 30,
        processed_ids: list[str] | None = None,
        follow_threads: bool = True,
    ) -> SmartSearchResult:
        ...
```

---

## LangGraph Checkpointing

LangGraph checkpoints persist graph state between runs using SQLite (`~/.agent-ls/checkpoints.db`). This enables:

- **Cross-run dedup**: `processed_message_ids` persists across invocations with the same `thread_id`
- **Incremental processing**: Second run for the same topic skips already-seen Slack messages
- **Thread identity**: `thread_id = f"agent-ls:{message_prefix}"` groups related runs

```toml
[checkpoint]
enabled = true
db_path = "~/.agent-ls/checkpoints.db"
max_age_days = 30
```

---

## Team Knowledge via Git

### Success-Gated Push

Every Obsidian write triggers a local git commit. But **only successful runs push** to the team remote:

- `finalize` node inspects state: no errors + at least one step completed → `run_success = True`
- `obsidian_write` checks `run_success`:
  - `True` → `commit_and_push()` (reaches team workspace)
  - `False` → `commit_file()` only (preserves work locally, doesn't pollute team)

### Freshness Fallback

When `kb_freshness` detects stale docs (broken commands, dead URLs):

1. Searches git history for recent successful commits matching the topic from **any team member**
2. If found, recovers the working content and writes it to the local vault
3. Pushes the recovered doc (this is itself a success)

```python
class TeamKnowledge:
    def find_working_setup(self, topic: str) -> Optional[WorkingSetup]:
        """Search git history for the most recent successful commit matching topic."""
        ...
```

The git repo is the team's collective memory. If your setup broke, someone else's working commit becomes the recovery source.

---

## Model Routing

| Task | Model Tier | Examples |
|------|-----------|----------|
| Intent classification | Cheap | Haiku, GPT-4o-mini, Ollama |
| Context extraction | Cheap | Parse Slack messages |
| Search query generation | Cheap | Form Slack search query |
| Plan generation | Expensive | Claude Sonnet/Opus |
| Computer Use execution | Expensive | Claude Sonnet (required) |
| Error diagnosis | Expensive | Analyze failures |
| Doc summarization | Cheap | Summarize setup results |

Config in `~/.agent-ls/config.toml`:
```toml
[models]
cheap = "bedrock/anthropic.claude-haiku-4-5-20251001"
expensive = "bedrock/anthropic.claude-sonnet-4-20250514"

[bedrock]
endpoint_url = "https://..."
auth_token = "..."
region = "us-west-2"
```

---

## Project Structure

```
agent-ls/
├── pyproject.toml
├── src/agent_ls/
│   ├── __main__.py            # Entry point
│   ├── cli.py                 # Typer CLI
│   ├── config/
│   │   ├── settings.py        # Pydantic settings (models, slack, obsidian, checkpoint)
│   │   └── allowlist.yaml     # Command allowlist
│   ├── graph/
│   │   ├── state.py           # AgentState
│   │   ├── builder.py         # LangGraph construction + checkpointer
│   │   ├── checkpointer.py    # SQLite checkpoint factory
│   │   ├── router.py          # Intent classifier
│   │   └── nodes/
│   │       ├── execute.py     # Computer Use loop
│   │       ├── plan.py        # Plan generation
│   │       ├── search.py      # Smart Slack search node
│   │       ├── finalize.py    # run_success determination
│   │       ├── kb_freshness.py # Freshness check + team fallback
│   │       ├── obsidian.py    # Vault read/write + git push gating
│   │       └── share.py       # Slack posting
│   ├── security/
│   │   ├── allowlist.py       # Pattern matching
│   │   ├── classifier.py      # Risk scoring
│   │   └── audit.py           # JSONL audit log
│   ├── integrations/
│   │   ├── slack/
│   │   │   ├── client.py      # Slack Web API + thread replies
│   │   │   ├── search.py      # Raw paginated search
│   │   │   ├── smart_search.py # Thread-following, dedup, ranking
│   │   │   └── formatter.py   # Obsidian → Slack mrkdwn
│   │   ├── obsidian/
│   │   │   ├── vault.py       # Vault CRUD
│   │   │   ├── templates.py   # Doc templates
│   │   │   ├── git_sync.py    # Git ops + history search + commit_and_push
│   │   │   └── team_knowledge.py # Team git history fallback
│   │   ├── computer_use/      # Subprocess executor
│   │   └── models/            # Multi-provider LLM clients
│   └── tui/
│       ├── app.py             # Textual App
│       ├── graph_runner.py    # Runs graph with checkpoint + thread_id
│       ├── screens/           # Main, approval, config
│       └── widgets/           # Chat, command log, status
├── tests/
└── docs/
```

---

## Security Model

### Command Allowlist System

**Allowlist-based** (`config/allowlist.yaml`):
- **Auto-approve**: `brew install *`, `git clone *`, `mkdir -p *`, `pip install *`, `nvm install *`, read-only commands
- **Require approval**: `sudo *`, `rm -rf *`, `defaults write *`, `curl|sh`
- **Blocked always**: `rm -rf /`, known destructive patterns

### Approval Flow

```
Command → Allowlist Check → Auto-approve? → Execute
                         → Unknown?      → TUI Modal [y/n/always] → Execute or Skip
                         → Blocked?      → Reject + Log
```

### Audit Log

All commands logged to `~/.agent-ls/audit.jsonl`:
```json
{"timestamp": "2026-05-27T14:30:00Z", "command": "brew install node", "classification": "auto_approve", "executed": true, "exit_code": 0, "duration_ms": 4523}
```

---

## Data Flows

### Flow 1: New Employee Setup
```
User triggers "setup" → Agent queries Slack profile for team/role →
Smart searches team channels (thread-following, dedup) →
Cheap model extracts steps → Reads existing Obsidian KB for that team →
Expensive model generates execution plan → Execute with approval gates →
Finalize (determine success) → Write setup log to Obsidian →
Success? → Git push to team workspace
```

### Flow 2: Knowledge Recovery (Freshness Fallback)
```
Read Obsidian docs → Extract commands/URLs → Test them (which, curl -I) →
Identify broken items → Search git history for working version from team →
Found? → Write recovered content to Obsidian → Push to team workspace
Not found? → Report "no team knowledge available"
```

### Flow 3: Share Doc to Slack
```
Read Obsidian .md file → Convert wikilinks/callouts to Slack mrkdwn →
Post to specified channel
```

---

## TUI Layout (Textual)

```
┌─ agent-ls ──────────────────────────────────────────────────────┐
│ Model: haiku/sonnet   Status: executing    [Ctrl+? for help]    │
├─────────────────────────────────────────────────────────────────┤
│ [Chat Panel]                                                     │
│   Agent: Setting up Java dev environment. Plan:                  │
│     1. [x] Install Homebrew        (2.1s)                        │
│     2. [x] Install Java 21         (45s)                         │
│     3. [ ] Install Bazel           (running...)                   │
│     4. [ ] Clone repos                                           │
│                                                                   │
│   $ brew install bazel                                           │
│   > Downloading bazel-7.4.0... ████████░░░░ 78%                  │
├─────────────────────────────────────────────────────────────────┤
│ [Command Log]                                                    │
│   14:30:01 [AUTO] brew install openjdk@21    exit=0  2.1s        │
│   14:30:04 [AUTO] brew install bazel         running...          │
├─────────────────────────────────────────────────────────────────┤
│ > Type a message...     [Ctrl+C: abort] [Ctrl+A: approve all]   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration

```toml
[models]
cheap = "bedrock/anthropic.claude-haiku-4-5-20251001"
expensive = "bedrock/anthropic.claude-sonnet-4-20250514"

[bedrock]
endpoint_url = "https://..."
auth_token = "..."
region = "us-west-2"

[slack]
user_token = "xoxp-..."
follow_threads = true
semantic_threshold = 0.3

[obsidian]
vault_path = "~/obsidian-vault"
git_auto_sync = true
git_push_on_success = true
freshness_fallback = true

[checkpoint]
enabled = true
db_path = "~/.agent-ls/checkpoints.db"
max_age_days = 30

[ui]
theme = "dark"
```

---

## Key Dependencies

```
langgraph>=0.4, langgraph-checkpoint-sqlite>=2.0
langchain-core>=0.3, langchain-anthropic>=0.3
langchain-openai>=0.3, langchain-aws>=0.2
boto3>=1.35, python-dotenv>=1.0
textual>=3.0, rich>=13.0
slack-sdk>=3.30
typer>=0.12, pydantic>=2.0, pydantic-settings>=2.0
gitpython>=3.1, structlog>=24.0, pyyaml>=6.0, httpx>=0.27
```

---

## Verification

- **Unit tests**: Allowlist pattern matching, smart search dedup/ranking, team knowledge git search, finalize logic
- **Integration tests**: Full graph execution with mocked LLM, checkpoint persistence across runs, git push gating
- **Manual**: Run `agent-ls "install node"` end-to-end, verify TUI renders, confirm Obsidian write + git push on success, verify second run deduplicates
