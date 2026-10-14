# Define runtime agents

Do not code or activate anything. Read only the necessary product, security, and data contracts. Prefer one agent with routing; split only genuinely distinct responsibilities or permissions.

For each agent define its bounded purpose, inputs, `output schema`, permissions, side effects, human approval, `invalid_output_policy`, and `Verification`. Use Pydantic for structured output consumed by Python, or an equivalent typed validator.

MCP capabilities remain `deferred`, allowlisted, and bounded by `MCP_POLICY.yaml`. Separate design, implementation, and `Activation`, then request approval for the minimal proposal.
