# Polyfork MCP server

Polyfork also serves the catalogue as an MCP server. It answers questions and returns URLs;
it never writes files, so vendoring still goes through `pf.py vendor`. Prefer `pf.py` when a
skill has to work in every harness; use the MCP server when native tools in one harness are
wanted.

- Endpoint: `https://polyfork.dev/mcp` (Streamable HTTP, 12 tools: `search_assets`,
  `get_asset`, `find_matching`, `get_variant`, `preview_scene`, `list_kits`, `get_kit`,
  `get_terrain`, `who_am_i`, `buy_plan`, `get_help`, `report_need`).
- A lighter endpoint with 4 place-building tools: `https://polyfork.dev/mcp/world`.
- `buy_plan` returns a Stripe checkout link. Never call it unless the user asks to buy.
- With a key configured as a header, paid downloads come back as signed links that expire
  after 15 minutes, so the agent never sees the key.

## Per harness, scoped to one project

| Harness | Project-scoped config |
|---|---|
| Claude Code | `claude mcp add --scope project --transport http polyfork https://polyfork.dev/mcp` writes `.mcp.json`. Key: `"headers": {"Authorization": "Bearer ${POLYFORK_API_KEY}"}` (environment expansion). |
| Codex | `.codex/config.toml` with `[mcp_servers.polyfork]`, `url = "https://polyfork.dev/mcp"`, `bearer_token_env_var = "POLYFORK_API_KEY"`. Loaded only for trusted projects. |
| pi | No built-in MCP. An extension such as `pi-mcp-adapter` (reads `.mcp.json`) is required; otherwise use `pf.py`. |

Do not add the server at user/global scope unless the user asks: it would appear in every
project.
