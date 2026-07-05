# agent-ls

AI-powered developer environment setup agent. Uses LLM-driven workflows to actively set up your dev environment on macOS — pulling context from Slack, executing commands with security gates, and maintaining a living knowledge base in Obsidian.

## Quick Start

### 1. Install dependencies

```bash
# Requires Python 3.12+ and uv
uv sync
```

### 2. Configure your environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

| Variable | Required | Description |
|----------|----------|-------------|
| `BEDROCK_ENDPOINT_URL` | Yes | Your Bedrock gateway endpoint |
| `BEDROCK_AUTH_TOKEN` | Yes | Auth token for the Bedrock gateway |
| `AWS_REGION` | No | Defaults to `us-west-2` |
| `BEDROCK_MODEL_CHEAP` | No | Fast model for classification (default: `anthropic.claude-haiku-4-5-20251001`) |
| `BEDROCK_MODEL_EXPENSIVE` | No | Smart model for planning (default: `anthropic.claude-sonnet-4-20250514`) |
| `SLACK_USER_TOKEN` | For Slack | Slack user OAuth token (`xoxp-...`) for searching team channels |
| `OBSIDIAN_VAULT_PATH` | For KB | Path to your Obsidian vault directory |

**Alternative providers** (instead of Bedrock):
- Set `ANTHROPIC_API_KEY` for direct Anthropic API access
- Set `OLLAMA_BASE_URL` for local models via Ollama

### 3. Create your Obsidian vault

The vault directory in `OBSIDIAN_VAULT_PATH` must exist — it is not auto-created.
Setup logs and the `.sh` harness are written into its `logs/` folder, and git-sync
expects a repo:

```bash
mkdir -p ~/Documents/ObsidianVault/logs      # match OBSIDIAN_VAULT_PATH
git -C ~/Documents/ObsidianVault init -q
```

### 4. Run the agent

```bash
# Launch the TUI
agent-ls run

# Or with an initial instruction
agent-ls run "set up my Java development environment"

# Full team setup
agent-ls setup --team platform-team
```

> **Slack is optional.** Setup runs (and the `.sh` harness) work without a Slack
> token — `SLACK_USER_TOKEN` is only needed for the search/share features and for
> auto-detecting your team from your Slack profile. Leave the `xoxp-...` placeholder
> in place to test setup without it.

For a full from-scratch walkthrough and troubleshooting, see
**[`docs/SETUP.md`](docs/SETUP.md)**.

## Usage

### Interactive TUI

The agent launches a terminal UI with:
- **Chat panel** — talk to the agent, see its plan and responses
- **Command log** — real-time streaming of command output
- **Plan checklist** — tracks progress through setup steps
- **DAG view** — shows which workflow node is active

### Key Bindings

| Key | Action |
|-----|--------|
| Enter | Send message |
| Ctrl+C | Quit |
| Ctrl+A | Approve all pending commands |
| Ctrl+L | Clear chat |
| Ctrl+P | Open configuration |
| Ctrl+S | View audit log |
| Tab | Switch focus between panels |

### Slash Commands

Type these in the input bar:

| Command | Description |
|---------|-------------|
| `/config` | Open configuration screen |
| `/theme dark\|light` | Switch UI theme |
| `/audit` | View security audit log |
| `/history` | List past sessions |
| `/share <file> <channel>` | Share an Obsidian doc to Slack |
| `/update-kb` | Trigger knowledge base freshness check |

### CLI Commands

```bash
# Launch TUI
agent-ls run [message] [--config] [--theme dark|light] [--resume SESSION_ID]

# Team setup shortcut
agent-ls setup [--team TEAM_NAME]

# Share Obsidian doc to Slack
agent-ls share path/to/doc.md "#channel-name"

# View past sessions
agent-ls history

# View audit log (last 20 entries)
agent-ls audit [-n 50]
```

## How It Works

1. **You describe what you need** — "set up Python 3.12 with pyenv and poetry"
2. **Agent searches for context** — queries Slack channels for team setup docs
3. **Agent generates a plan** — step-by-step commands with explanations
4. **Commands execute with security gates**:
   - Safe commands (`brew install`, `git clone`) auto-execute
   - Risky commands (`sudo`, `rm -rf`) require your approval
   - Dangerous commands (`rm -rf /`) are blocked
5. **Results are logged** — to Obsidian KB and audit trail. Each setup run also emits an executable, re-runnable `{team}-setup-{date}.sh` bash harness containing only the audited commands that succeeded; failed, blocked, and manual steps are commented out (with secrets redacted) so a teammate can review the full context and replay the working setup.
6. **You can resume interrupted sessions** — `agent-ls run --resume <id>`

## Security Model

All commands are checked against an allowlist before execution:

- **Auto-approve**: `brew install *`, `git clone *`, `pip install *`, `mkdir`, `ls`, `cat`
- **Require approval**: `sudo *`, `rm -rf *`, `defaults write *`, `curl | sh`
- **Blocked always**: `rm -rf /`, fork bombs, raw disk writes

Every command is logged to `~/.agent-ls/audit.jsonl` with timestamp, classification, exit code, and duration.

## Configuration

Settings are stored in `~/.agent-ls/config.toml` (auto-created on first use). You can edit it directly or use `Ctrl+P` in the TUI:

```toml
[models]
cheap = "bedrock/anthropic.claude-haiku-4-5-20251001"
expensive = "bedrock/anthropic.claude-sonnet-4-20250514"

[bedrock]
endpoint_url = "https://your-bedrock-endpoint"
region = "us-west-2"

[slack]
user_token = "xoxp-..."

[obsidian]
vault_path = "~/Documents/ObsidianVault"
git_auto_sync = true

[ui]
theme = "dark"
session_persistence = true
```

Environment variables in `.env` override `config.toml` values.

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Run linter
ruff check src/ tests/

# Run type checker
mypy src/
```

## Project Structure

```
src/agent_ls/
├── cli.py                 # Typer CLI entry point
├── config/                # Settings + command allowlist
├── graph/                 # LangGraph state machine (nodes + routing)
├── integrations/          # Slack, Obsidian, model router, executor
├── security/              # Allowlist, risk classifier, audit log
└── tui/                   # Textual TUI (screens, widgets, themes)
```
