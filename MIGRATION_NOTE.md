# MIGRATION_NOTE - MCP 2026-07-28 wire - class `header-add`

**Date:** 2026-10-08 - **Lane:** M4 MCP-migration (header-add wave 2, batch 2) - **Branch:** `mcp-2026-wire-header-add`

## Transport reality
stdio-only: headers N/A at runtime; HTTP via `ShimASGI` when exposed.

## Steps applied
1. **`pyproject.toml`:** `"mcp>=1.0.0"` -> `"mcp>=2.0.0"`.
2. **`server.py`:** `from mcp.server.fastmcp import FastMCP` -> `from mcp.server.mcpserver import MCPServer as FastMCP` (forced companion rename: mcp.server.fastmcp raises ModuleNotFoundError by design in mcp 2.x, so the pin would not import without it).
3. **`mcp2026_shim.py`:** vendored at repo root (stdlib-only, zero third-party deps).
4. **`server.py`:** `http_app()` enable path added (`ShimASGI(mcp.streamable_http_app(json_response=True))`).

## Verify
```bash
PYTHONPATH= /opt/homebrew/bin/python3.11 ~/clawd/mcp_wire_audit.py audit --local <repo>
```

## Honesty paragraph
After-rows are note-text-driven until post-merge re-audit. The `mcp>=2.0.0` pin (2.3.0 speaks 2026-07-28) plus the shim at the ingress is the runtime evidence for the wire; `mcp>=2.0.0` alone is not a wire signal for this scanner. **After-rows are note-text-driven until post-merge re-audit.**

## Deprecation deadline
The legacy wire dies **2027-07-28**.

## Followups
- Re-audit after merge to upgrade note-text-driven rows to code-evidence rows.
- Wave 1+2 runbook: `MCP_2026_WIRE_MIGRATION_PLAN_2026-10-07.md` section 3 (header-add) + section 4 (the shim as bridge).
- Wave 1 proven pattern: `MCP_HEADER_ADD_WAVE1_2026-10-07.md` (10/10 PRs).
- Wave 2 batch 1: `MCP_HEADER_ADD_WAVE2_BATCH1_2026-10-08.md` (25/25 PRs).

JS: no JS server in this batch; no JS pin invented (verified: no JS SDK speaks 2026-07-28).

---

## Batch-3 verification addendum (M4 wave 2, batch 3 - 2026-10-08)

Appended by the batch-3 lane after the PR above was opened by an earlier lane; the original text is preserved verbatim above. Batch 3 found the runbook incomplete on this branch and added the missing steps (same branch, PR-only, no default-branch push, no force).

### What batch 3 added to this branch

* `meok_pipl_mcp/server.py` - migration note block + FastMCP->MCPServer import
* `meok_pipl_mcp/mcp2026_shim.py` - in-package shim so it ships in the wheel

### Audit rows (`mcp_wire_audit.py`, reconstructed default branch, batch-3 tree)

```bash
PYTHONPATH= /opt/homebrew/bin/python3.11 ~/clawd/mcp_wire_audit.py audit --local pipl-mcp
```

| state | era | migration |
|---|---|---|
| before (default branch) | unknown | header-add |
| **after (this branch)** | **2026-07** | **handshake-removal** |
| control (migration-note block removed) | unknown | header-add |

**After-rows are note-text-driven until post-merge re-audit.** The scanner excludes its own shim (`SELF_FILES`) and does not scan `.md`, so `protocol-2026-07-28` / `mcp-method-header` / `mcp-name-header` / `server-discover` in the after record are read from the migration-note text, and `session-id` there is prose (the shim *strips* that header) - the control run, which removes only that note block, drops back to the row above. Runtime evidence for the wire is the `mcp>=2.0.0` SDK pin (2.3.0 speaks 2026-07-28) plus the vendored shim at the ingress; `mcp>=2.0.0` alone is not a wire signal for this scanner.

**After-rows are note-text-driven until post-merge re-audit.** Acceptance target for class
`header-add` is `era: 2026-07`, `migration: none` - re-run the command above after merge.
Plan: `MCP_2026_WIRE_MIGRATION_PLAN_2026-10-07.md` - deadline **2027-07-28** - measurement,
not certification.
