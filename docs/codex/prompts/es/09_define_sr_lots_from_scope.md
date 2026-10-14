# Definir lotes SR 4.1

No programes. Lee el `AGENTS.md`, la solicitud relevante y el posible `SR_LOTS.yaml`; consulta solo los archivos imprescindibles.

Distingue capacidad nueva y reparación. `existing_requirement_repair` reabre el lote; `validated_requests` sigue siendo un campo de compatibilidad. Propón el mínimo de lotes coherentes con objetivo, `Scope`, criterios observables, dependencias, `Verification`, `Activation`, decisiones humanas y condiciones de parada.

No añadas una gate documental autónoma. El núcleo no depende de MCP; las capacidades externas siguen `MCP_POLICY.yaml`. Usa `task_state.yaml` solo para continuidad útil y valida el contrato.
