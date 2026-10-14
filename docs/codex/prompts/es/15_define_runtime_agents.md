# Definir agentes runtime

No programes ni actives nada. Lee solo los contratos necesarios de producto, seguridad y datos. Prefiere un agente con routing; separa únicamente responsabilidades o permisos realmente distintos.

Define para cada agente propósito, entradas, `output schema`, permisos, efectos secundarios, aprobación humana, `invalid_output_policy` y `Verification`. Usa Pydantic para salidas estructuradas consumidas por Python o un validador tipado equivalente.

Las capacidades MCP permanecen `deferred`, en allowlist y limitadas por `MCP_POLICY.yaml`. Separa diseño, implementación y `Activation`, y solicita aprobación sobre la propuesta mínima.
