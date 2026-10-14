# Definir lotes SR 4.1

Não programe. Leia o `AGENTS.md`, a solicitação relevante e o possível `SR_LOTS.yaml`; consulte apenas os arquivos indispensáveis.

Separe nova capacidade de reparo. `existing_requirement_repair` reabre o lote; `validated_requests` continua como campo de compatibilidade. Proponha o mínimo de lotes coerentes com objetivo, `Scope`, critérios observáveis, dependências, `Verification`, `Activation`, decisões humanas e condições de parada.

Não adicione uma gate documental autônoma. O núcleo não depende de MCP; capacidades externas seguem `MCP_POLICY.yaml`. Use `task_state.yaml` apenas para continuidade útil e valide o contrato.
