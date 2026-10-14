# Definir passes SR 4.1

Não programe. Leia o `AGENTS.md` aplicável, `SR_LOTS.yaml` e o possível `SR_PASSES.yaml`; abra arquivos do produto ou `task_state.yaml` somente quando necessário.

Agrupe lotes `repair`, `reopened` ou `validated` no mínimo de passes coerentes. Para cada um, informe objetivo, `Scope`, dependências, `Verification` final, `Activation` separada, decisões humanas e condições reais de parada.

Não crie uma gate documental autônoma. Campos históricos servem apenas para compatibilidade. O núcleo não depende de MCP; capacidades externas seguem `MCP_POLICY.yaml`.

Proponha o diff, respeite a aprovação aplicável e valide o contrato.
