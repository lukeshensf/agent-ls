# agent-ls Hardening Backlog

This is the **hardening backlog** referenced by [`SETUP.md`](SETUP.md). The codebase
is **feature-complete**; the remaining work is hardening — greening the quality
gates, closing security gaps in the command-execution path, and adding regression
coverage. Do **not** add features and do **not** re-architect;
[`architecture.md`](architecture.md) is the design contract.

## How to use this file (for automated runs)

- Each **numbered checklist item** under a phase is **exactly one deliverable = one PR**.
- Pick the **first** item that is (a) unblocked, (b) not already claimed by an open/merged
  PR or a `feat/*`/`fix/*` branch ahead of `origin/main`, and (c) not checked `[x]`.
- Respect the **`Depends on:`** line — never start an item whose dependency is still open.
- When a PR merges, check the box `[x]` **in the same PR that implements the item** (so
  `main` always reflects reality) and paste the merged PR number next to it.
- **Definition of done for every item:** `pytest` fully green, no **new** `ruff` or `mypy`
  errors beyond the documented baseline (and fewer, if the item targets them), no unresolved
  HIGH/CRITICAL security finding on the diff, and the existing security gates
  (`security/allowlist.py`, `security/classifier.py`, `security/audit.py`,
  `config/allowlist.yaml`) never weakened.

## Baseline (captured 2026-07-05, commit `757d5ef`)

Run from the repo root with the project venv:

```
.venv/bin/python -m pytest -q      # 185 passed
.venv/bin/ruff check src/ tests/   # 23 errors (18 F401, 4 F841, 1 E402)
.venv/bin/mypy src/                # 28 errors in 16 files
```

The test suite is green. **Lint and types are NOT clean** — Phase 1 exists to fix that
so later phases can enforce "no new errors." Any item that reduces the ruff/mypy count
must record the new count in its PR body.

---

## Phase 1 — Green the quality gates

Goal: `ruff check` and `mypy src/` both exit clean, so every later PR can be held to a
zero-regression bar. These are low-risk, high-leverage, and mostly mechanical.

- [x] **1.1 — Clear all `ruff` F401 unused-import errors.** _(merged in #3)_ Remove the 18 unused imports
  ruff flags across `src/` and `tests/` (e.g. `computer_use/executor.py:4`,
  `obsidian/team_knowledge.py:4`, `slack/smart_search.py:4-5`, `tui/app.py:3`,
  `tui/widgets/plan_checklist.py:3`, and several `tests/unit/*`). Do **not** delete an
  import that is actually re-exported; verify with `ruff check`. Acceptance: F401 count → 0,
  `pytest` still 185 passed.

- [x] **1.2 — Clear `ruff` F841/E402 errors.** _(merged in #3)_ Fix the 4 unused-variable findings
  (`graph/nodes/execute.py:61` `timer`, `graph/nodes/summarize.py:10` `execution_log`,
  `tests/unit/test_kb_freshness.py:84-85`) and the 1 module-import-not-at-top finding
  (`__main__.py:5`). For `execute.py:61`, the `ExecutionTimer` is assigned but its
  `elapsed_ms` is never read — decide whether to record its duration into the audit entry
  (preferred, since `_execute_command` already logs `duration_ms`) or drop the `with`.
  Do not change behavior silently; if a variable was meant to be used, wire it in.
  Depends on: 1.1. Acceptance: `ruff check src/ tests/` → **0 errors**.

- [x] **1.3 — Add a `[tool.mypy]` config and install `types-PyYAML`.** _(merged in #4)_ Add a `[tool.mypy]`
  section to `pyproject.toml` (`python_version = "3.12"`, `ignore_missing_imports` scoped
  narrowly or per-module overrides for `boto3`/`botocore`/`langchain_ollama`), and add
  `types-PyYAML` to the dev dependency group so the `yaml` import-untyped errors
  (`security/allowlist.py:8`, `security/dynamic_allowlist.py:7`,
  `obsidian/templates.py:9`, `obsidian/team_profiles.py:6`) resolve. Do **not** blanket-suppress
  real type errors — only silence third-party stubs that genuinely lack them. Acceptance:
  the import-untyped/import-not-found mypy errors are gone; the remaining count is recorded.

- [x] **1.4 — Fix the `audit.py` typed-dict assignment errors.** _(merged in #5)_ `AuditLogger.log_command`
  builds `entry` whose value type mypy infers as `bool | str`, then assigns `int`
  (`audit.py:35,37`). Give `entry` an explicit `dict[str, object]` (or a `TypedDict`)
  annotation so `exit_code`/`duration_ms` int assignments type-check. Security-sensitive
  file — change types only, never the redaction/logging behavior. Depends on: 1.3.
  Acceptance: `audit.py` mypy errors → 0.

- [x] **1.5 — Fix the LLM-response `str | list` type errors in graph nodes.** _(merged in #6)_ `router.py:34,42`,
  `nodes/plan.py:44,52`, `nodes/extract.py:47`, `nodes/error_recovery.py:55`,
  `nodes/context_gather.py:45`, and `nodes/search.py:29` all treat a LangChain message
  `.content` (typed `str | list[...]`) as a plain `str`. Add a small shared helper (e.g.
  `_as_text(content) -> str`) that coerces list-of-parts content to a string, and route
  these call sites through it. Depends on: 1.3. Acceptance: those 8 mypy errors → 0;
  add a unit test for the helper covering both the `str` and `list` shapes.

- [x] **1.6 — Fix the TUI/config/router remaining mypy errors.** _(merged in #8)_ Address
  `tui/screens/config.py:160-175` (dict passed where a pydantic settings sub-model is
  expected — construct the sub-models), `tui/screens/audit_viewer.py:103` (`Row.style`),
  `tui/app.py:100,199` (`str | None` and `GraphRunner`/`None` assignment),
  `slack/client.py:37` (return type), and `models/router.py:157` (unexpected `model`
  kwarg). Fix the actual types — **no `# type: ignore`**. Depends on: 1.3, 1.5.
  Acceptance: `mypy src/` → **0 errors** (this item closes out Phase 1).

---

## Phase 2 — Security-gate hardening

Goal: close real gaps in the command-execution trust boundary. **Never weaken a gate to
pass a test** — if a security test fails, the code is wrong. Every item here needs a
regression test that would fail before the fix.

- [x] **2.1 — Block allowlist bypass via command chaining.** _(merged in #7)_ `AllowlistChecker.classify()`
  (`security/allowlist.py`) `fnmatch`-matches the **entire** command string, and
  `graph/nodes/execute.py` passes the whole line to `create_subprocess_shell`. So
  `brew install foo && rm -rf ~` matches `brew install *` and **auto-approves** a
  destructive tail. Fix by splitting the command on shell operators (`;`, `&&`, `||`, `|`,
  newline) **before** classification and classifying **each** segment, returning the
  most-restrictive result (BLOCKED > NEEDS_APPROVAL > AUTO_APPROVE). Keep existing single-command
  behavior identical. Add tests: chained safe+destructive → NEEDS_APPROVAL/BLOCKED; the
  existing `curl * | sh` require-approval rule must still fire. Acceptance: new bypass test
  fails on `main`, passes after; all existing `test_security.py` cases stay green.

- [x] **2.2 — Harden the risk classifier against evasion.** _(merged in #9)_ `security/classifier.py` uses
  naive substring checks (`"sudo" in command`, `"rm " in command`). It misses
  tab/newline-separated tokens, `\t`sudo, and quoted/backslash-escaped variants, and
  `PIPE_TO_SHELL`/`SUBSHELL_SUDO` only `.match` from the start. Normalize whitespace and
  anchor the regexes with `.search` where appropriate so evasive spacing still scores.
  This **raises** scores only (never lowers an existing detection). Depends on: 2.1
  (shared normalization helper if introduced there). Acceptance: add tests for
  `sudo\trm`, `RM  -RF`, mid-line `... | sh`; no existing score assertion regresses.

- [x] **2.3 — Add path-traversal guards to `ObsidianVault`.** `vault.read`/`write`
  (`integrations/obsidian/vault.py`) join a caller-supplied `relative_path` to the vault
  root with no containment check, so `../../etc/passwd` escapes the vault. Mirror the
  containment check already used in `emit_harness_node` (`resolve()` +
  `is_relative_to(root)`), raising `ValueError` on escape. Acceptance: tests for `..`
  traversal and absolute-path inputs on both `read` and `write`; existing vault tests green.

- [ ] **2.4 — Replace bare `except Exception` in git sync and harness emit.**
  `git_sync.commit_and_push` catches `(GitCommandError, Exception)` and
  `emit_harness_node` catches `(ValueError, Exception)` — both swallow *everything*,
  masking bugs (and `(X, Exception)` is redundant since `Exception` already covers `X`).
  Narrow to the git/OS exceptions actually expected, log the type, and let programming
  errors surface. Do **not** change the success-gating semantics (failed push must still
  not flip `run_success`). Acceptance: a test that a `KeyboardInterrupt`/`TypeError` is
  not silently swallowed; git-push-gating tests still green.

---

## Phase 3 — Robustness & correctness

Goal: fix latent correctness issues surfaced during the survey. Lower blast radius than
Phase 2 but each needs a test.

- [ ] **3.1 — Record execution duration via the audit timer, not a discarded var.**
  Tie off the `ExecutionTimer` decision from 1.2: ensure `_execute_command`
  (`graph/nodes/execute.py`) logs a duration sourced consistently (executor
  `duration_ms` vs. `ExecutionTimer.elapsed_ms`) and document which is authoritative.
  Depends on: 1.2. Acceptance: audit entry always carries `duration_ms`; unit test asserts it.

- [x] **3.2 — Make `GitSync.search_history` timestamp parsing correct.** In
  `git_sync.py`, `GitHistoryEntry.timestamp` is set to `parts[3]` (the ISO date) only when
  4 parts are present, else `""`, and `message` falls back to `parts[2]` — the field
  mapping is fragile when a commit subject contains `|`. Parse with a bounded
  `split("|", 3)` contract and cover the `|`-in-subject case with a test. Acceptance:
  regression test with a pipe in the commit message; `test_team_knowledge.py` green.
  _Resolved: reordered the log format from `%H|%an|%s|%aI` to `%H|%an|%aI|%s` so the
  free-form subject is last, then unpack with a bounded `split("|", 3)`. This fixed two
  bugs: (1) even with no pipe, `message` was previously the date and the subject was
  dropped; (2) a `|` in the subject corrupted both fields. New
  `tests/unit/test_git_sync_history.py` drives the real parser (previously only mocked)
  against a real repo, covering plain and pipe-containing subjects._

- [ ] **3.3 — Guard `CommandExecutor.execute` timeout cleanup.** In
  `computer_use/executor.py`, the `except asyncio.TimeoutError` branch calls `proc.kill()`
  but never awaits `proc.wait()`, risking a zombie/unclosed-transport warning; and if the
  subprocess fails to *spawn*, `proc` is unbound in the handler. Await the process after
  kill and scope the handler so an un-spawned proc can't `NameError`. Acceptance: a test
  driving the timeout path (short timeout on a sleep) that asserts `timed_out=True` and no
  unraised exception.

---

## Phase 4 — Coverage, CI, and docs

Goal: lock in the gains so regressions can't silently return.

- [ ] **4.1 — Add a GitHub Actions CI workflow.** Add `.github/workflows/ci.yml` that runs
  `uv sync` then `pytest -q`, `ruff check src/ tests/`, and `mypy src/` on push/PR against
  `main`. Do not add new runtime deps. Depends on: 1.6 (mypy must be clean or CI will be
  red on arrival). Acceptance: workflow file validates; commands mirror `docs/SETUP.md §6`.

- [ ] **4.2 — Add a security-focused regression test module.** Consolidate the
  execution-path attack cases (chaining bypass, classifier evasion, vault traversal) into a
  dedicated `tests/unit/test_security_regressions.py` so future edits to the gate are
  covered by intent-named tests. Depends on: 2.1, 2.2, 2.3. Acceptance: module added,
  every case maps to a Phase-2 fix, suite green.

- [ ] **4.3 — Document the security model precisely in `docs/`.** Expand the security
  section (in `architecture.md` or a new `docs/SECURITY.md`) to state the trust boundary:
  segment-level allowlist classification, most-restrictive-wins, secret redaction in the
  harness, and the success-gated push. Docs-only. Depends on: 2.1, 2.4. Acceptance: doc
  reflects the shipped behavior of Phases 2–3; no code change.

---

## Out of scope (do not do under this backlog)

- New features, new nodes, new integrations, or new CLI commands.
- Renaming/relocating modules or changing the LangGraph node topology.
- Weakening any allowlist/classifier/audit rule to make a test pass.
- Bundling multiple checklist items into one PR.
