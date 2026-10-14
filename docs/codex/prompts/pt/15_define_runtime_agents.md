# Definir agentes runtime

Não programe nem ative nada. Leia somente os contratos necessários de produto, segurança e dados. Prefira um agente com routing; separe apenas responsabilidades ou permissões realmente distintas.

Defina para cada agente objetivo, entradas, `output schema`, permissões, efeitos colaterais, aprovação humana, `invalid_output_policy` e `Verification`. Use Pydantic para saída estruturada consumida por Python ou um validador tipado equivalente.

Capacidades MCP permanecem `deferred`, em allowlist e limitadas por `MCP_POLICY.yaml`. Separe desenho, implementação e `Activation`, depois peça aprovação da proposta mínima.
