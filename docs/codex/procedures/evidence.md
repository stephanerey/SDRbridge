# Evidence and knowledge

Use the cheapest source that can decide the question:

1. known target file or observed error;
2. focused search and real source;
3. existing test, runtime log or generated artifact;
4. RepoMap only when navigation remains uncertain;
5. Nexus KG only when `knowledge.mode: nexus_kg` and `MCP_POLICY.yaml` enables a resolved read capability.

In `core` mode, make no MCP call. In `nexus_kg` mode, perform one bounded query per source state, reuse it across gates, prefer structured paginated results and fall back to source without repeated retries.

RepoMap and KG orient navigation; source and proportionate final verification decide the result.
