# agent-ls — Setup & Developer Guide

A from-scratch walkthrough to get agent-ls running on a fresh macOS machine, plus
the troubleshooting notes that aren't obvious from the code. If you just want the
one-line version, see the Quick Start in [`../README.md`](../README.md); this
document is the fuller onboarding path.

> **Platform:** macOS only. **Runtime:** Python 3.12+ with [`uv`](https://docs.astral.sh/uv/).

---

## 1. Install

```bash
git clone git@github.com:lukeshensf/agent-ls.git
cd agent-ls
uv sync            # creates .venv/ and installs all deps (incl. dev tools)
```

This produces a `.venv/`. All commands below assume you invoke tools through it
(`.venv/bin/python`, `.venv/bin/pytest`, …) or that you've activated it.

---

## 2. Configure credentials (`.env`)

```bash
cp .env.example .env
```

Then edit `.env`. What's actually **required** depends on what you want to test:

| Variable | Required for | Notes |
|----------|--------------|-------|
| `BEDROCK_ENDPOINT_URL` | **All LLM use** | Bedrock gateway endpoint. Without it the agent can't plan. |
| `BEDROCK_AUTH_TOKEN` | **All LLM use** | Token for the gateway. |
| `AWS_REGION` | No | Defaults to `us-west-2`. |
| `BEDROCK_MODEL_CHEAP` / `BEDROCK_MODEL_EXPENSIVE` | No | Sensible defaults ship in `config/settings.py`. |
| `OBSIDIAN_VAULT_PATH` | Writing the KB + harness | Path to a local Obsidian vault dir (see step 3). |
| `SLACK_USER_TOKEN` | **Only** Slack context/search/share | `xoxp-…`. Setup + harness work **without** it (see below). |

**Alternative LLM providers** (instead of Bedrock): set `ANTHROPIC_API_KEY` for
the direct Anthropic API, or `OLLAMA_BASE_URL` for local models via Ollama.

Precedence: environment variables in `.env` **override** anything in
`~/.agent-ls/config.toml`.

### Slack is optional

`SLACK_USER_TOKEN` ships as the placeholder `xoxp-...`. You do **not** need to
replace it to test a setup run: the `context_gather` node degrades gracefully to
an empty user context when Slack isn't configured, and the whole
setup → plan → execute → emit_harness → obsidian_write flow still works. Slack is
only needed for the `search` and `share` intents and for auto-detecting your
team/role from your Slack profile.

To wire it up later: create a Slack app → **OAuth & Permissions** → install to the
workspace → copy the **User OAuth Token**. Scopes: `search:read`, `chat:write`,
`users:read`. Put it in `.env` as `SLACK_USER_TOKEN=xoxp-…`.

---

## 3. Create the Obsidian vault

The vault directory referenced by `OBSIDIAN_VAULT_PATH` must **exist** — it is not
auto-created. Setup runs write both a markdown log and the `.sh` harness into its
`logs/` subdirectory, and git-sync expects a repo:

```bash
# Use whatever path you set for OBSIDIAN_VAULT_PATH; default in .env.example:
mkdir -p ~/Documents/ObsidianVault/logs
git -C ~/Documents/ObsidianVault init -q
```

If the vault isn't a git repo, `git_auto_sync` logs a warning and skips syncing —
the local file write still succeeds, so this is optional for a first smoke test
but recommended so team-sync behaves as designed.

---

## 4. Run it

Launch the TUI with an initial instruction:

```bash
.venv/bin/python -m agent_ls run "install jq with homebrew and verify it"
```

or, since the console script is installed by `uv sync`:

```bash
.venv/bin/agent-ls run "install jq with homebrew and verify it"
```

Both load `.env` automatically (a Typer callback in `cli.py` calls `load_dotenv()`
before any command). What happens on a `setup`-intent run:

1. Bedrock generates a step-by-step plan.
2. Each command is checked against the allowlist — safe commands
   (`brew install`, `git clone`, …) auto-run; risky ones (`sudo`, `rm -rf`) prompt
   you in the approval modal; dangerous ones (`rm -rf /`) are blocked.
3. Results are written to the vault as **both**:
   - `logs/{team}-setup-{date}.md` — human-readable log
   - `logs/{team}-setup-{date}.sh` — a re-runnable bash harness (see below)
4. On a successful run with `git_auto_sync` on, the vault is committed and pushed;
   failed runs commit locally only.

Inspect the generated harness:

```bash
cat ~/Documents/ObsidianVault/logs/*-setup-*.sh
```

### Other commands

```bash
.venv/bin/agent-ls setup --team platform-team   # team-scoped setup
.venv/bin/agent-ls share path/to/doc.md "#chan"  # share a vault doc to Slack
.venv/bin/agent-ls history                        # list past sessions
.venv/bin/agent-ls audit -n 50                    # tail the security audit log
```

---

## 5. The re-runnable harness (`.sh`)

Every setup run emits a standalone, executable bash script alongside the markdown
log. It's designed so a teammate can reproduce your setup **without** the agent:

- Header carries provenance (team, date, agent-ls version, source) and the script
  runs with `#!/usr/bin/env bash` + `set -euo pipefail`.
- Only commands that **passed the allowlist and succeeded** (`exit 0`) are emitted
  as live commands, in order.
- Failed, blocked, skipped, and manual steps are emitted as **commented-out** lines
  with a precise note (e.g. `# SKIPPED (failed, exit=1): …`), so the script stays
  runnable yet shows the full picture.
- Known credentials (Bedrock auth token, Slack token) are **redacted** on every
  line, including comments — the harness never contains secrets.

---

## 6. Development workflow

```bash
.venv/bin/python -m pytest -q          # full test suite
.venv/bin/ruff check src/ tests/       # lint
.venv/bin/mypy src/                     # type check
```

See [`PLAN.md`](PLAN.md) for the current hardening backlog and
[`architecture.md`](architecture.md) for the design contract (node graph, state,
security model). Do not re-architect against that contract.

---

## Troubleshooting

| Symptom | Cause & fix |
|---------|-------------|
| Agent errors immediately / no LLM response | `BEDROCK_ENDPOINT_URL` or `BEDROCK_AUTH_TOKEN` missing/blank in `.env`. Verify with the snippet below. |
| Credentials seem ignored | You're running an old build where only `python -m agent_ls` loaded `.env`. Current builds load it for `agent-ls` too. Pull latest. |
| `obsidian_write`/harness fails to write | `OBSIDIAN_VAULT_PATH` directory doesn't exist — create it (step 3). |
| `git_sync_failed` warning | Vault isn't a git repo, or has no remote. `git init` it (step 3); add a remote to enable push. |
| Slack search/share does nothing | `SLACK_USER_TOKEN` still the `xoxp-...` placeholder — set a real token (step 2). |

**Verify your config resolves** (masks secret values):

```bash
.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from agent_ls.config.settings import Settings
s = Settings.from_toml()
mask = lambda v: f'SET (len={len(v)})' if v else 'MISSING'
print('bedrock.endpoint_url:', mask(s.bedrock.endpoint_url))
print('bedrock.auth_token  :', mask(s.bedrock.auth_token))
print('slack.user_token    :', mask(s.slack.user_token))
print('obsidian.vault_path :', s.obsidian.vault_path)
"
```
