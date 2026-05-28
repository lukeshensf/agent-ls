# agent-ls: Architecture & Implementation Plan

## Context

Employees joining teams waste hours deciphering outdated Slack messages and broken setup docs. agent-ls is a local-first CLI/TUI tool that uses LLM-powered agentic workflows to actively set up developer environments on macOS, pulling context from Slack, executing commands with security gates, and maintaining a living knowledge base in Obsidian (Git-synced).

**Key constraints**: macOS-only, local-first, TUI interface, Python/LangGraph, configurable model routing, allowlist-based security, 1-2 week POC timeline.

---

## System Architecture

### LangGraph State Machine

```
[START] -> [ROUTER] --(intent)--> [CONTEXT_GATHER] -> [PLAN] -> [EXECUTE <-> SECURITY_GATE] -> [OBSIDIAN_WRITE] -> [SUMMARIZE] -> [END]
                     |                    |                                                          ^
                     |                    +-- calls --> [SLACKBOT SERVICE] (external)                |
                     |                    +-- reads --> [OBSIDIAN KB] (local)                        |
                     |                                                                              |
                     +--(search)--> [SLACKBOT SERVICE] -> [EXTRACT] --------------------------------|
                     |                                                                              |
                     +--(share)---> [OBSIDIAN_READ] -> [SLACK_SHARE] -------------------------------|
                     |                                                                              |
                     +--(update)--> [KB_FRESHNESS_CHECK] -> [OBSIDIAN_WRITE] ----------------------+
```

**Nodes:**
1. `router` - Classifies user intent (cheap model)
2. `context_gather` - Pulls user context from Slack profile/channels (cheap model)
3. `plan` - Generates step-by-step execution plan (expensive model)
4. `execute` - Runs commands via subprocess, inner loop: execute -> observe -> decide_next (expensive model / Computer Use)
5. `security_gate` - Checks commands against allowlist, blocks/prompts for dangerous ones
6. `slack_search` - Searches Slack for setup docs (cheap model for query formation)
7. `extract` - Summarizes Slack results into actionable steps (cheap model)
8. `obsidian_read` / `obsidian_write` - CRUD on vault markdown files
9. `slack_share` - Posts formatted docs to Slack channels
10. `summarize` - Produces human-readable session summary

**State:**
```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_context: UserContext  # team, role, stack
    intent: str
    plan: list[PlanStep]
    current_step: int
    command_queue: list[Command]
    execution_log: list[ExecutionResult]
    approval_pending: Optional[Command]
    obsidian_docs: list[str]
    slack_results: list[SlackMessage]
```

### Model Routing

| Task | Model Tier | Examples |
|------|-----------|----------|
| Intent classification | Cheap | Haiku, GPT-4o-mini, Ollama |
| Context extraction | Cheap | Parse Slack messages |
| Plan generation | Expensive | Claude Sonnet/Opus |
| Computer Use execution | Expensive | Claude Sonnet (required) |
| Error diagnosis | Expensive | Analyze failures |
| Doc summarization | Cheap | Summarize setup results |

Config in `~/.agent-ls/config.toml`:
```toml
[models]
cheap = "anthropic/claude-haiku"
expensive = "anthropic/claude-sonnet"

[models.ollama]
base_url = "http://localhost:11434"
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
│   │   ├── settings.py        # Pydantic settings
│   │   └── allowlist.yaml     # Command allowlist
│   ├── graph/
│   │   ├── state.py           # AgentState
│   │   ├── builder.py         # LangGraph construction
│   │   ├── router.py          # Intent classifier
│   │   └── nodes/
│   │       ├── execute.py     # Computer Use loop
│   │       ├── plan.py        # Plan generation
│   │       ├── search.py      # Slack search
│   │       ├── obsidian.py    # Vault read/write
│   │       └── share.py       # Slack posting
│   ├── security/
│   │   ├── allowlist.py       # Pattern matching
│   │   ├── classifier.py      # Risk scoring
│   │   └── audit.py           # JSONL audit log
│   ├── integrations/
│   │   ├── slack/             # Slack Web API
│   │   ├── obsidian/          # Vault ops + git sync
│   │   ├── computer_use/      # Subprocess executor
│   │   └── models/            # Multi-provider LLM clients
│   └── tui/
│       ├── app.py             # Textual App
│       ├── screens/           # Main, approval, config
│       └── widgets/           # Chat, command log, status
├── tests/
└── docs/
```

---

## Security Model

### Command Allowlist System

**Allowlist-based** (`config/allowlist.yaml`):
- **Auto-approve**: `brew install *`, `git clone *`, `mkdir -p *`, `pip install *`, `nvm install *`, read-only commands (`ls`, `cat`, `which`, `echo`)
- **Require approval**: `sudo *`, `rm -rf *`, `defaults write *`, `curl|sh`, anything modifying `/etc/`
- **Blocked always**: `rm -rf /`, known destructive patterns
- **Contextual**: `export *`, `echo >> *` analyzed by cheap model for risk

### Approval Flow

```
Command -> Allowlist Check -> Auto-approve? -> Execute
                           -> Unknown?      -> TUI Modal [y/n/always] -> Execute or Skip
                           -> Blocked?      -> Reject + Log
```

### Audit Log

All commands logged to `~/.agent-ls/audit.jsonl`:
```json
{"timestamp": "2026-05-27T14:30:00Z", "command": "brew install node", "classification": "auto_approve", "executed": true, "exit_code": 0, "duration_ms": 4523}
{"timestamp": "2026-05-27T14:30:05Z", "command": "sudo xcode-select --install", "classification": "needs_approval", "user_approved": true, "executed": true, "exit_code": 0}
{"timestamp": "2026-05-27T14:32:00Z", "command": "rm -rf /", "classification": "blocked", "executed": false, "reason": "Blocked: recursive deletion of root"}
```

---

## Data Flow: Slack <-> Agent <-> Obsidian

### Flow 1: New Employee Setup
```
User triggers "setup" -> Agent queries Slack profile for team/role ->
Searches team channels for setup docs -> Cheap model extracts steps ->
Reads existing Obsidian KB for that team -> Merges Slack + KB info ->
Expensive model generates execution plan -> Execute with approval gates ->
Write setup log to Obsidian -> Optionally share summary to Slack
```

### Flow 2: Auto-Update KB
```
Read Obsidian docs -> Extract commands/URLs -> Test them (which, curl -I) ->
Identify broken items -> Search Slack for recent fixes ->
Expensive model proposes update -> Write fix to Obsidian ->
Post notification to team Slack channel
```

### Flow 3: Share Doc to Slack
```
Read Obsidian .md file -> Convert wikilinks/callouts to Slack mrkdwn ->
Post to specified channel -> Update doc frontmatter with share metadata
```

---

## TUI Layout (Textual)

### Main Screen
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

### Approval Modal
```
┌──────────── Command Approval Required ────────────────┐
│                                                        │
│  The agent wants to run:                               │
│                                                        │
│  $ sudo xcode-select --install                         │
│                                                        │
│  Risk: MEDIUM                                          │
│  Reason: Requires elevated privileges (sudo)           │
│  Context: Installing Xcode CLI tools for compilation   │
│                                                        │
│  [y] Approve   [n] Reject   [a] Always allow this     │
└────────────────────────────────────────────────────────┘
```

### Key Bindings

| Key | Action |
|-----|--------|
| Enter | Send message / confirm |
| Ctrl+C | Abort current operation |
| Ctrl+A | Approve all pending (batch) |
| Tab | Toggle focus between panels |
| Ctrl+L | Clear chat |
| Ctrl+P | Show/hide plan panel |
| Ctrl+S | Show security audit log |
| q / Ctrl+D | Quit |

---

## Implementation Phases

---

### FRONTEND (TUI + CLI)

#### Frontend Phase 1: Scaffold & Static Shell (Days 1-2)
- Set up Textual app skeleton (`tui/app.py`)
- Implement static layout: header bar, chat panel, command log panel, input bar
- Wire Typer CLI (`cli.py`) to launch TUI via `agent-ls` command
- Key bindings: Ctrl+C quit, Tab panel focus, Ctrl+L clear
- **Verify**: `agent-ls` launches TUI with placeholder content, keybindings work

#### Frontend Phase 2: Approval Modal & Interactive Input (Days 3-4)
- Build approval modal screen (`tui/screens/approval.py`) with risk level, command, context, [y/n/a] buttons
- Build input widget with message submission (Enter to send)
- Wire approval modal to an event bus (pub/sub pattern for backend integration)
- Add status bar widget showing model name + execution state
- **Verify**: Type message -> appears in chat. Trigger mock approval -> modal renders correctly.

#### Frontend Phase 3: Live Streaming & Progress (Days 7-8)
- Wire TUI to real backend graph events via async queue
- Stream command stdout/stderr into command log in real-time
- Render plan as checklist with live progress ([x] done, [ ] pending, [~] running)
- Progress bars for long-running commands
- **Verify**: Run `agent-ls "install node"` -> see live output, plan updates, completion

#### Frontend Phase 4: Configuration & Polish (Days 13-14)
- Config screen (`tui/screens/config.py`) for model selection, vault path, Slack token
- History: scroll back through previous messages/commands
- Audit log viewer (Ctrl+S to view `audit.jsonl` formatted)
- Error states: network failure, LLM timeout, command failure UI
- **Verify**: Change model in config screen -> next call uses new model. Scroll history works.

#### Frontend Phase 5: Advanced UX (Weeks 3-4)
- Multi-step workflow visualization (DAG view of LangGraph nodes)
- Notification toasts for background KB updates
- Slash commands in input (`/share`, `/update-kb`, `/config`)
- Theme support (dark/light)
- Session persistence (resume interrupted setups)

---

### BACKEND (LangGraph + Integrations)

#### Backend Phase 1: Project Foundation (Days 1-2)
- Initialize project: `pyproject.toml` with uv, package structure under `src/agent_ls/`
- Pydantic settings (`config/settings.py`) loading from `~/.agent-ls/config.toml`
- Structured logging setup with structlog
- Basic CLI entry point (`__main__.py`, `cli.py` with Typer)
- **Verify**: `python -m agent_ls --help` works, settings load from TOML

#### Backend Phase 2: Security Core (Days 3-4)
- `config/allowlist.yaml` — define safe/dangerous/blocked command patterns
- `security/allowlist.py` — glob pattern matcher, risk classification enum
- `security/audit.py` — append-only JSONL logger (`~/.agent-ls/audit.jsonl`)
- `integrations/computer_use/executor.py` — async subprocess runner with timeout, output capture
- Unit tests for allowlist matching (exact, glob, edge cases)
- **Verify**: Pattern matcher correctly classifies `brew install x` (auto), `sudo x` (approval), `rm -rf /` (blocked)

#### Backend Phase 3: LangGraph Core (Days 5-6)
- `graph/state.py` — AgentState TypedDict with all fields
- `graph/router.py` — intent classification node (calls cheap model)
- `graph/nodes/plan.py` — plan generation node (calls expensive model)
- `graph/nodes/execute.py` — execution loop: generate command -> security check -> execute -> observe -> loop or finish
- `graph/builder.py` — wire nodes with conditional edges, compile graph
- `integrations/models/router.py` — model routing logic (cheap vs expensive per task)
- Anthropic client wrapper for Claude calls
- **Verify**: Feed "install python" -> graph produces plan -> executes `brew install python` -> logs result

#### Backend Phase 4: Slack Integration (Days 8-9)
- `integrations/slack/client.py` — Slack Web API client with user OAuth token
- `integrations/slack/search.py` — `search.messages` API with pagination, filtering
- `graph/nodes/search.py` — Slack search node (forms query, paginates, returns raw messages)
- `graph/nodes/extract.py` — context extraction node (cheap model parses Slack messages into structured steps)
- **Verify**: Search for "python setup" in a test channel -> returns relevant messages -> extraction produces actionable steps

#### Backend Phase 5: Obsidian Integration (Days 10-11)
- `integrations/obsidian/vault.py` — find vault path, read/write/list markdown files, frontmatter parsing
- `integrations/obsidian/templates.py` — doc templates (setup guide, daily log, design doc)
- `integrations/obsidian/git_sync.py` — git pull before read, git add + commit + push after write
- `graph/nodes/obsidian.py` — read/write nodes wired into graph
- **Verify**: Agent writes setup log to vault -> file exists with correct content -> git commit created

#### Backend Phase 6: Model Routing & Multi-Provider (Day 12)
- `integrations/models/openai.py` — OpenAI client wrapper
- `integrations/models/ollama.py` — Ollama client wrapper (local model)
- Config-driven model selection: change `config.toml` -> different model used
- Fallback logic: if primary model fails, try secondary
- **Verify**: Set cheap model to Ollama -> intent classification uses local model. Set to Haiku -> uses Anthropic API.

#### Backend Phase 7: Slack Sharing & End-to-End (Days 13-14)
- `integrations/slack/formatter.py` — Obsidian markdown -> Slack mrkdwn converter (wikilinks, callouts, code blocks)
- `graph/nodes/share.py` — post formatted doc to Slack channel
- Full end-to-end integration test: user input -> Slack search -> plan -> execute -> Obsidian write -> Slack share
- **Verify**: `agent-ls share vault/setup-guide.md #team-channel` posts formatted content to Slack

#### Backend Phase 8: Auto-Updating KB (Weeks 3-4)
- Scheduled freshness checks: extract commands/URLs from Obsidian docs, test them
- Broken link detection and Slack search for fixes
- Auto-update docs with "last verified" timestamps
- "Approve & Remember" — dynamically expand allowlist from TUI approvals
- Error recovery: agent proposes fixes for failed commands
- Team profiles: pre-configured setup recipes per team (loaded from Obsidian)

---

### Integration Milestones

| Milestone | Frontend Phase | Backend Phase | When |
|-----------|---------------|---------------|------|
| Static TUI launches | F1 | B1 | Day 2 |
| Commands execute with approval | F2 | B2 + B3 | Day 6 |
| Live streaming in TUI | F3 | B3 | Day 8 |
| Slack search works end-to-end | F3 | B4 | Day 9 |
| Obsidian docs written | F3 | B5 | Day 11 |
| Full flow with sharing | F4 | B7 | Day 14 |

---

### SLACKBOT INTEGRATION (Context Retrieval Service)

#### Overview

Instead of agent-ls directly using a Slack User OAuth token to search messages, agent-ls delegates context retrieval to an **existing Slackbot service**. The Slackbot has full workspace access (messages, channel history, user profiles, pinned items, team bookmarks) and returns structured context that agent-ls feeds into its planning pipeline.

This decouples agent-ls from Slack auth complexity, centralizes rate limiting, and enables richer context than the `search.messages` API alone provides.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  agent-ls (local CLI/TUI)                                           │
│                                                                      │
│  [User Input] → [Router] → [Context Gather] → [Plan] → [Execute]   │
│                                    │                                 │
│                                    │ request context                 │
│                                    ▼                                 │
│                          ┌─────────────────┐                        │
│                          │ SlackBot Client  │                        │
│                          │ (adapter layer)  │                        │
│                          └────────┬────────┘                        │
└───────────────────────────────────┼─────────────────────────────────┘
                                    │
                     ───────────────┼───────────────
                    │   Network (HTTP or Slack API)  │
                     ───────────────┼───────────────
                                    │
                                    ▼
              ┌─────────────────────────────────────────┐
              │  Slackbot Service (existing, deployed)   │
              │                                         │
              │  Capabilities:                          │
              │  • Search messages across workspace     │
              │  • Read full channel history            │
              │  • Get user profiles & team info        │
              │  • Access pinned items & bookmarks      │
              │  • Return structured context payloads   │
              └─────────────────────────────────────────┘
```

#### Communication Patterns (Two Options)

**Option A: Direct HTTP API (Recommended for low-latency)**

The Slackbot exposes a REST endpoint that agent-ls calls directly:

```
POST https://<slackbot-service>/api/context
{
  "query": "java development setup",
  "team": "platform-team",
  "scope": ["messages", "pins", "bookmarks"],
  "max_results": 50,
  "channels": ["#team-platform", "#dev-setup", "#onboarding"]
}

Response:
{
  "messages": [...],
  "pins": [...],
  "bookmarks": [...],
  "user_profiles": [...],
  "suggested_channels": [...]
}
```

**Option B: Slack-mediated (Bot mention / DM)**

agent-ls sends a structured message to the bot via Slack, the bot replies in-thread:

```
agent-ls → DM to @setup-bot:
  "CONTEXT_REQUEST: java development setup for platform-team"

@setup-bot replies:
  {structured JSON context payload}
```

This is simpler (no separate endpoint to manage) but higher latency and limited by Slack message size (40KB).

#### Integration Design

**New files:**

| File | Purpose |
|------|---------|
| `integrations/slack/bot_client.py` | Adapter that calls the Slackbot service for context |
| `graph/nodes/context_gather.py` | Updated: routes to bot_client instead of direct search |

**SlackBotClient interface:**

```python
class SlackBotClient:
    """Client for the external Slackbot context retrieval service."""

    def __init__(self, endpoint_url: str = None, bot_user_id: str = None):
        # Option A: HTTP endpoint
        # Option B: Slack bot user ID for DM-based communication
        ...

    async def fetch_context(
        self,
        query: str,
        team: str | None = None,
        channels: list[str] | None = None,
        scope: list[str] = ["messages", "pins", "bookmarks"],
        max_results: int = 50,
    ) -> BotContextResponse:
        """Request workspace context from the Slackbot."""
        ...

    async def get_team_setup_docs(self, team: str) -> list[SetupDoc]:
        """Ask the bot for team-specific setup documentation."""
        ...

    async def get_user_context(self, user_email: str) -> UserWorkspaceContext:
        """Get a user's team, role, and relevant channels from the bot."""
        ...
```

**Response types:**

```python
@dataclass
class BotContextResponse:
    messages: list[SlackMessage]
    pins: list[PinnedItem]
    bookmarks: list[Bookmark]
    user_profiles: list[dict]
    suggested_channels: list[str]
    confidence: float  # 0-1 relevance score

@dataclass
class SetupDoc:
    title: str
    content: str
    source_channel: str
    last_updated: str
    verified: bool

@dataclass
class UserWorkspaceContext:
    team: str
    role: str
    channels: list[str]
    tech_stack: list[str]
    manager: str | None
```

#### Updated Data Flow

**Before (direct Slack API):**
```
User → Router → Search Slack (user token) → Extract → Plan → Execute
```

**After (via Slackbot):**
```
User → Router → Context Gather (calls Slackbot) → Plan → Execute
                       │
                       ├─ fetch_context(query, team)     → messages, pins
                       ├─ get_team_setup_docs(team)      → verified guides
                       └─ get_user_context(user_email)   → role, stack
```

The Slackbot provides richer context than raw search — it can aggregate across pinned items, bookmarks, channel topics, and its own indexed knowledge, giving the planning LLM better signal.

#### Configuration

```toml
[slackbot]
# Option A: HTTP endpoint
endpoint_url = "https://your-slackbot-service.internal/api"
auth_token = "bot-service-auth-token"

# Option B: Slack-mediated (DM to bot)
bot_user_id = "U1234567890"

# Shared
timeout_seconds = 30
max_retries = 3
```

Environment variables:
```bash
SLACKBOT_ENDPOINT_URL=https://your-slackbot-service.internal/api
SLACKBOT_AUTH_TOKEN=...
SLACKBOT_USER_ID=U1234567890
```

#### Implementation Phases

##### Slackbot Phase 1: Adapter Layer (Days 1-2)
- `integrations/slack/bot_client.py` — HTTP client with auth, retry, timeout
- `BotContextResponse` dataclass and response parsing
- Config: add `SlackBotSettings` to settings.py
- Unit tests with mocked HTTP responses
- **Verify**: Mock bot returns JSON → client parses into typed response

##### Slackbot Phase 2: Graph Integration (Days 3-4)
- Update `graph/nodes/context_gather.py` to use `SlackBotClient` as primary source
- Fallback: if bot is unreachable, fall back to direct Slack search (graceful degradation)
- Merge bot context with user's local Obsidian KB for comprehensive plan input
- Update `AgentState` with `bot_context: Optional[BotContextResponse]`
- **Verify**: `agent-ls "set up Java"` → calls bot → receives context → generates better plan

##### Slackbot Phase 3: Rich Context (Days 5-6)
- `get_team_setup_docs()` — fetch verified team guides from bot's knowledge base
- `get_user_context()` — auto-detect user's team/role/stack without manual config
- Pre-populate `UserContext` from bot response before plan generation
- Cache bot responses locally (TTL: 1 hour) to reduce latency on repeated queries
- **Verify**: New user runs agent-ls → bot identifies their team → auto-fetches relevant docs

##### Slackbot Phase 4: Feedback Loop (Week 3)
- After successful setup, notify bot of completion (POST /api/feedback)
- Bot can update its knowledge base with verified steps
- Bot can proactively notify agent-ls of stale docs (webhook or polling)
- **Verify**: Complete setup → bot receives success signal → marks docs as verified

---

## Key Dependencies

```
langgraph>=0.4, langchain-core>=0.3, langchain-anthropic>=0.3
langchain-openai>=0.3, langchain-aws>=0.2
boto3>=1.35, python-dotenv>=1.0
textual>=3.0, rich>=13.0
slack-sdk>=3.30
typer>=0.12, pydantic>=2.0, pydantic-settings>=2.0
gitpython>=3.1, structlog>=24.0, pyyaml>=6.0, httpx>=0.27
```

---

## Verification

- **Unit tests**: Allowlist pattern matching, intent classification, state transitions, markdown conversion
- **Integration tests**: Full graph execution with mocked LLM, real subprocess execution of safe commands, Obsidian vault CRUD on temp dir
- **Manual**: Run `agent-ls "install node"` end-to-end, verify TUI renders, confirm audit log, test approval modal, test Ctrl+C abort
