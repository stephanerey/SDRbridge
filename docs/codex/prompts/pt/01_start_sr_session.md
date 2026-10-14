# Retomar uma sessão SR

Não programar antes da validação do escopo. Ler `AGENTS.md`, `CURRENT_STATE` e o resultado `selected` de `find_next_session_prompt.py --root . --json`; se for `ambiguous`, pedir o caminho exato. Ler o `task_state.yaml` ativo ou somente os contratos históricos necessários, incluindo `validated_requests` abertas.

Separar implementação, evidências e aceitação humana: implementação incompleta é `repair`; `user_testing` exige trabalho técnico completo. Propor um único escopo coerente, sua verificação e a autorização necessária. Não criar micro-lote para retorno sobre requisito existente. Carregar `NEXT_SESSION_PROMPT.md` e `procedures/resume.md` apenas quando houver necessidade de continuidade.
