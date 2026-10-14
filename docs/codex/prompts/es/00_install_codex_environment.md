# Instalar SR Method 4.1 en un proyecto nuevo

No programar. Instalar la versión publicada `4.1.0`, verificarla y detenerse antes del trabajo de aplicación. Leer el `AGENTS.md` más cercano, seleccionar `SR_PACK_SOURCE` explícitamente y registrar `release_status`, `source_commit` y estado Git. Rechazar una fuente que no coincida con la release esperada. Si existe un marcador SR, usar `05_upgrade_codex_environment.md`.

Previsualizar, informar creaciones y preservaciones, esperar la autorización exacta y después usar `--write`:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

El destino debe incluir `SR_LOTS.yaml`, `SR_PASSES.yaml` con `passes: []`, `MCP_POLICY.yaml` en modo `core` y `task_state.yaml`. No inventar lotes, pases, requisitos ni capacidades MCP. No cambiar código, secretos, migraciones, dependencias ni despliegues de la aplicación. Flujo: `00 -> 06` o `05 -> 06 -> 07`.
