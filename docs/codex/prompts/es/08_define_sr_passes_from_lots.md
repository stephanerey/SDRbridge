# Definir pases SR 4.1

No programes. Lee el `AGENTS.md` aplicable, `SR_LOTS.yaml` y el posible `SR_PASSES.yaml`; abre archivos de producto o `task_state.yaml` solo cuando sea necesario.

Agrupa lotes `repair`, `reopened` o `validated` en el mínimo de pases coherentes. Para cada uno indica objetivo, `Scope`, dependencias, `Verification` final, `Activation` separada, decisiones humanas y condiciones reales de parada.

No crees una gate documental autónoma. Los campos históricos son solo de compatibilidad. El núcleo no depende de MCP; las capacidades externas siguen `MCP_POLICY.yaml`.

Propón el diff, respeta la aprobación aplicable y valida el contrato.
