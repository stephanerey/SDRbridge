# SR Agent Method 4.1

For product agents, prompts, RAG or runtime tool orchestration, first apply the normal Scope Gate. Then use `AI_AGENT_RUNTIME_METHOD.md` for product-specific contracts.

Keep Codex method skills separate from runtime-agent skills. Runtime tools must declare bounded actions, schemas, permissions, side effects, approval policy and final validation. Never let a model generate and execute unrestricted SQL.

For MCP-backed runtime tools, follow the product's MCP policy; the SR method does not invent server capabilities or tool names.
