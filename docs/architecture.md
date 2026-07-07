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
                       [EMIT_HARNESS]
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
9. `emit_harness` — Serializes plan into a re-runnable bash harness (`logs/{team}-setup-{date}.sh`), executable, git-synced with same success gate
10. `obsidian_write` — Writes to vault, commits, conditionally pushes
11. `kb_freshness` — Checks docs for staleness, falls back to team git history
12. `obsidian_read` / `slack_share` — Read vault docs, post to Slack

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

The security model establishes a trust boundary around command execution and file operations, protecting against malicious or erroneous commands from the LLM-generated plans. All hardening work shipped in Phase 2 is documented below.

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

### Command Chaining Defense

The allowlist classifier defends against chained-command bypass attacks by splitting shell command lines on operators (`;`, `&&`, `||`, `|`, `&`, newlines) and classifying each segment independently before execution (`src/agent_ls/security/allowlist.py`).

**Most-restrictive-wins rule:** The final classification is the most restrictive verdict across all segments:
1. If any segment is **BLOCKED**, the entire command is blocked
2. If any segment is **NEEDS_APPROVAL** (and none are blocked), the entire command requires approval
3. Only if all segments are **AUTO_APPROVE** does the command auto-approve

**Example:** The command `brew install foo && rm -rf ~` is split into two segments:
- Segment 1: `brew install foo` → AUTO_APPROVE
- Segment 2: `rm -rf ~` → BLOCKED

The most-restrictive verdict (BLOCKED) wins, so the entire command is blocked. This prevents an approved command head from smuggling a destructive tail past the gate.

### Evasion Resistance

The risk classifier normalizes commands before pattern matching to resist evasion attempts (`src/agent_ls/security/classifier.py`):

- **Whitespace normalization:** All whitespace (tabs, multiple spaces, newlines) is collapsed to single spaces before classification. This prevents evasive spacing like `sudo\trm` or `rm  -rf` from bypassing destructive-command detection.
- **Case-insensitive matching:** Pattern matching for pipe-to-shell, system redirects, and subshell escalation uses `re.IGNORECASE` so `SUDO` or `RM` variants are caught.
- **Mid-line pattern matching:** Patterns use `re.search` (not `re.match`) so pipe-to-shell sequences like `curl | sh` are detected anywhere in the command, not just at the start.

### Obsidian Vault Containment

All Obsidian vault read/write operations enforce path containment to prevent directory traversal attacks (`src/agent_ls/integrations/obsidian/vault.py`):

- **Containment check:** Every caller-supplied relative path is resolved via `Path.resolve()` and verified to be contained within the vault root using `Path.is_relative_to()`.
- **Escape rejection:** Paths with `..` components or absolute paths that escape the vault boundary raise `ValueError` before any filesystem operation.
- **Defense-in-depth:** The `_safe_path` method applies this check uniformly across `read`, `write`, `list_docs`, and `exists` operations.

This guards against untrusted input (e.g., LLM-extracted team slugs from Slack profiles) being used in file paths.

### Audit Log

All executed commands (approved or auto-approved) are logged to `~/.agent-ls/audit.jsonl` with classification, exit code, and duration. Blocked commands are logged but never executed.

```json
{"timestamp": "2026-05-27T14:30:00Z", "command": "brew install node", "classification": "auto_approve", "executed": true, "exit_code": 0, "duration_ms": 4523}
```

### Success-Gated Push

The `finalize` node determines `run_success` based on error state and whether any plan steps completed successfully (`src/agent_ls/graph/nodes/finalize.py`). The `obsidian_write` and `emit_harness` nodes use this flag to gate git push operations (`src/agent_ls/graph/nodes/obsidian.py`, `src/agent_ls/graph/nodes/emit_harness.py`):

- **Success:** If `run_success = True`, both the setup log and the emitted bash harness are committed and pushed to the team's remote workspace.
- **Failure:** If `run_success = False`, artifacts are committed locally but never pushed, preventing failed runs from polluting the shared team knowledge base.

### Secret Redaction in Emitted Harness

The emitted bash harness (`logs/<team>-setup-<date>.sh`) redacts sensitive credentials before writing to disk (`src/agent_ls/graph/nodes/emit_harness.py`):

- **Redacted secrets:** Bedrock auth tokens and Slack user tokens (from `config.toml`) are replaced with `***REDACTED***` in all command text and metadata.
- **Not redacted:** Endpoint URLs are not redacted because they are legitimate substrings of live commands (e.g., `curl <endpoint>/v1/models`) and are not secrets.
- **Scope:** Secret redaction applies to command text, step descriptions, and notes rendered on comment lines to prevent token leakage via LLM-echoed metadata.

### Narrow Exception Handling

Exception handlers are narrowed to catch only expected failure modes, allowing programming errors (e.g., `TypeError`, `AttributeError`) to surface rather than being masked:

- **git_sync.py:** `commit_and_push` catches `(GitError, OSError)` only — expected git and filesystem failures. Previously caught `(GitCommandError, Exception)`, which was redundant and overly broad.
- **emit_harness.py:** Git sync failure handler catches `(GitError, OSError, ValueError)` — expected git errors, filesystem errors, and the `ValueError` raised when the vault is not a git repo. Previously caught `(ValueError, Exception)`, which swallowed all programming errors.

---

## Data Flows

### Flow 1: New Employee Setup
```
User triggers "setup" → Agent queries Slack profile for team/role →
Smart searches team channels (thread-following, dedup) →
Cheap model extracts steps → Reads existing Obsidian KB for that team →
Expensive model generates execution plan → Execute with approval gates →
Finalize (determine success) → Emit re-runnable .sh harness →
Write setup log to Obsidian → Success? → Git push to team workspace
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
