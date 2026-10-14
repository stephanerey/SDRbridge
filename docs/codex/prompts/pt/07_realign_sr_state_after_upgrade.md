# Realinhar o estado SR após uma atualização

Começar em modo somente leitura. Ler `AGENTS.md`, `SR_BOOTSTRAP.md`, `CURRENT_STATE`, registros e o resultado `selected` de `find_next_session_prompt.py`; se for `ambiguous`, pedir o caminho e usar `--prompt`.

Ler `task_state.yaml` ativo ou contratos legacy necessários. Inventariar requisitos abertos, incluindo `validated_requests`, com implementação, evidências e aceitação. Propor o menor realinhamento e estados `repair`, `user_testing` ou `blocked`.

Aguardar a validação exata `je valide` antes de modificar. Depois alterar apenas memória e registros nomeados, nunca código da aplicação. Atualizar `CURRENT_STATE.md` somente com evidências. Não escolher retomada por data, converter histórico em massa nem criar micro-lote para requisito existente.
