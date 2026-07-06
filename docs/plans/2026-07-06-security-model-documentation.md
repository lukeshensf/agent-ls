# Document the security model precisely in docs/

**Deliverable:** PLAN 4.3 — Document the security model precisely in `docs/`

## Context

The agent-ls codebase has completed all security hardening work in Phase 2:
- 2.1: Segment-level allowlist classification with most-restrictive-wins for command chaining
- 2.2: Hardened risk classifier against evasion
- 2.3: Path-traversal guards on ObsidianVault
- 2.4: Narrowed bare exception handlers in git sync and harness emit

The existing `docs/architecture.md` contains a Security Model section (lines 250-273) that describes the basic allowlist system and approval flow, but it does not reflect the hardening improvements shipped in Phase 2. This deliverable expands that section to document the precise trust boundary and security guarantees after hardening.

## Acceptance criteria

- [ ] `docs/architecture.md` Security Model section is expanded to document:
  - Segment-level allowlist classification (how chained commands are split and classified independently)
  - Most-restrictive-wins rule (BLOCKED > NEEDS_APPROVAL > AUTO_APPROVE)
  - Secret redaction in the emitted harness (if implemented; verify in emit_harness node)
  - Success-gated push (only successful runs push to team workspace)
  - Path-traversal containment for Obsidian vault operations
  - Narrow exception handling (no bare `except Exception` masking bugs)
- [ ] All statements accurately reflect the shipped behavior (no aspirational language)
- [ ] No code changes (docs-only)
- [ ] Existing tests remain green (`pytest -q`)

## Implementation approach

1. **Read the Phase 2 implementation commits** to understand precisely what was shipped:
   - PR #7 (2.1): command chaining bypass fix — read `src/agent_ls/security/allowlist.py` for segment splitting logic
   - PR #9 (2.2): classifier evasion hardening — read `src/agent_ls/security/classifier.py` for normalization
   - PR #10 (2.3): vault path-traversal guards — read `src/agent_ls/integrations/obsidian/vault.py` for containment check
   - PR #13 (2.4): narrow exception handlers — read `src/agent_ls/integrations/obsidian/git_sync.py` and `src/agent_ls/graph/nodes/emit_harness.py`

2. **Read the current `docs/architecture.md` Security Model section** (lines 250-273) to understand what's already documented:
   - Command Allowlist System (auto-approve/require-approval/blocked)
   - Approval Flow diagram
   - Audit Log format
   
3. **Verify secret redaction in emit_harness**: Read `src/agent_ls/graph/nodes/emit_harness.py` to check if secrets are redacted from the emitted bash harness. If not implemented, do not document it as a feature.

4. **Expand the Security Model section** with new subsections:
   - Add a subsection **"Command Chaining Defense"** documenting:
     - How the allowlist classifier splits on shell operators (`;`, `&&`, `||`, `|`, newlines) before classification
     - Most-restrictive-wins rule: if any segment is BLOCKED, the entire command is BLOCKED; if any is NEEDS_APPROVAL, the entire command requires approval
     - Example: `brew install foo && rm -rf ~` → segments are classified independently → destructive segment blocks the entire command
   
   - Add a subsection **"Evasion Resistance"** documenting:
     - Whitespace normalization (tabs, multiple spaces) before classification
     - Case-insensitive pattern matching for destructive commands
     - Mid-line pattern matching (not just start-anchored) for pipe-to-shell detection
   
   - Add a subsection **"Obsidian Vault Containment"** documenting:
     - All vault read/write operations check that resolved paths are contained within vault root
     - Relative paths with `..` and absolute paths are rejected with `ValueError`
   
   - Expand the existing **"Audit Log"** subsection to document:
     - All executed commands (approved or auto-approved) are logged with classification, exit code, and duration
     - Blocked commands are logged but not executed
   
   - Expand or add a subsection **"Success-Gated Push"** documenting:
     - The `finalize` node determines `run_success` based on error state and completed steps
     - `obsidian_write` node only pushes to the team remote if `run_success = True`
     - Failed runs commit locally but never pollute the team workspace
     - Same gating applies to the emitted bash harness

5. **Verify accuracy**: Cross-reference each documented behavior against the actual code to ensure no aspirational statements.

6. **Commit the changes** with message: `docs: expand security model section (PLAN 4.3)`

## Files to modify

- `docs/architecture.md` — expand the Security Model section (lines 250-273) with new subsections as described above

## Risks

- **Documenting unshipped behavior**: If secret redaction was not actually implemented in `emit_harness.py`, do not document it. Only document what exists in the code.
- **Inaccurate descriptions**: Must read the actual implementation (not just commit messages) to ensure documented behavior matches reality.
- **Over-documentation**: Keep it concise and focused on the trust boundary. This is not a code walkthrough; it's a security model description for users and auditors.
