# Verificar una instalación SR 4.1

Modo `read_only`. No modificar, instalar, restaurar ni reparar archivos.

```bash
python3 scripts/codex/verify_codex_pack.py
python3 scripts/codex/validate_release_docs.py --root . --json
python3 scripts/codex/audit_codex_pack.py --root . --json
python3 scripts/codex/sr_post_install_check.py --root . --json
```

Verificar `4.1.0`, `AGENTS.md`, rutas, `MCP_POLICY.yaml`, `task_state.yaml`, lotes, pases, documentación localizada y preservación. SR Contract 3.1.0, contratos 3.0.0 y `audit_sr_task_contracts.py` siguen legibles como legacy. Informar pruebas, avisos, conflictos y límites, y detenerse sin reparar.
