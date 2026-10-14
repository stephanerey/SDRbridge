# Define SR 4.1 passes

Do not code. Read the applicable `AGENTS.md`, `SR_LOTS.yaml`, and any existing `SR_PASSES.yaml`; open product files or `task_state.yaml` only when genuinely needed.

Group `repair`, `reopened`, or `validated` lots into the fewest coherent passes. For each pass, state its objective, allowed `Scope`, dependencies, final `Verification`, separate `Activation`, human decisions, and real stop conditions.

Do not create a standalone documentation gate. Historical fields are compatibility only. The core method has no MCP dependency; external capabilities must follow `MCP_POLICY.yaml`.

Propose the diff, honor the applicable human approval, then validate the contract.
