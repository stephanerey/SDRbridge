# Atualizar uma instalação SR para 4.1

Não programar. Fazer uma instalação antiga, parcial, desconhecida ou adaptada convergir para a versão publicada `4.1.0` sem sobrescrever o projeto.

Ler o `AGENTS.md` mais próximo, marcadores SR, estado, lotes, passes e memória ativa. Selecionar `SR_PACK_SOURCE` explicitamente; registrar `release_status`, `source_commit` e estado Git. Visualizar:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
```

A versão anterior é apenas proveniência. Classificar conteúdo como `absent`, `managed`, `locally_modified`, `unmanaged`, `obsolete`, `conflict` ou `already_aligned`. Convergir conteúdo gerido reconhecido, reduzir o bloco SR de `AGENTS.md` e preservar código, segredos, dependências, estado do produto, histórico e skills locais. Remover obsoletos somente com impressão reconhecida. Reconciliar o perfil por capacidade; adicionar `MCP_POLICY.yaml` e `task_state.yaml`; manter contratos antigos legíveis.

Relatar plano, conflitos e preservações, e aguardar autorização exata. Depois:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --upgrade
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

Não fechar lotes nem executar build, deploy, migração ou chamada MCP. O post-check deve provar `4.1.0`, rotas, documentação, skills e preservação. Rótulos legacy `managed_update`, `already_current` e `reconciliation_required` continuam legíveis; nenhuma ramificação depende de versão como `2.2.0`. Depois usar `06_verify_sr_installation.md` e, apenas se necessário, `07_realign_sr_state_after_upgrade.md`.
