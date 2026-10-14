# Verificar uma instalação SR 4.1

Modo `read_only`. Não modificar, instalar, restaurar ou reparar arquivos.

```bash
python3 scripts/codex/verify_codex_pack.py
python3 scripts/codex/validate_release_docs.py --root . --json
python3 scripts/codex/audit_codex_pack.py --root . --json
python3 scripts/codex/sr_post_install_check.py --root . --json
```

Verificar `4.1.0`, `AGENTS.md`, rotas, `MCP_POLICY.yaml`, `task_state.yaml`, lotes, passes, documentação localizada e preservação. SR Contract 3.1.0, contratos 3.0.0 e `audit_sr_task_contracts.py` continuam legíveis como legacy. Relatar evidências, avisos, conflitos e limites, e parar sem reparar.
