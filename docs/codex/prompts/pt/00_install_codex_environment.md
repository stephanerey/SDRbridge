# Instalar SR Method 4.1 em um projeto novo

Não programar. Instalar a versão publicada `4.1.0`, verificar e parar antes do trabalho da aplicação. Ler o `AGENTS.md` mais próximo, selecionar `SR_PACK_SOURCE` explicitamente e registrar `release_status`, `source_commit` e estado Git. Recusar uma fonte que não corresponda à release esperada. Se houver marcador SR, usar `05_upgrade_codex_environment.md`.

Visualizar, relatar criações e preservações, aguardar autorização exata e depois usar `--write`:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

O destino deve incluir `SR_LOTS.yaml`, `SR_PASSES.yaml` com `passes: []`, `MCP_POLICY.yaml` em modo `core` e `task_state.yaml`. Não inventar lotes, passes, requisitos ou capacidades MCP. Não alterar código, segredos, migrações, dependências ou deploys da aplicação. Fluxo: `00 -> 06` ou `05 -> 06 -> 07`.
