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
