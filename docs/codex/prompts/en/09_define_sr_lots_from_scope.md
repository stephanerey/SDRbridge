# Define SR 4.1 lots

Do not code. Read the applicable `AGENTS.md`, the relevant request, and any existing `SR_LOTS.yaml`; inspect only essential product files.

Separate new capability from repair. `existing_requirement_repair` reopens the lot; `validated_requests` remains a compatibility field. Propose the fewest coherent lots, each with an objective, `Scope`, observable acceptance criteria, dependencies, `Verification`, separate `Activation`, human decisions, and stop conditions.

Do not add a standalone documentation gate. The core method has no MCP dependency; external capabilities follow `MCP_POLICY.yaml`. Use `task_state.yaml` only for useful continuity, then validate the contract.
