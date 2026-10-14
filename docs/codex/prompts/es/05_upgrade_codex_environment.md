# Actualizar una instalación SR a 4.1

No programar. Hacer converger una instalación antigua, parcial, desconocida o adaptada a la versión publicada `4.1.0` sin sobrescribir el proyecto.

Leer el `AGENTS.md` más cercano, marcadores SR, estado, lotes, pases y memoria activa. Seleccionar `SR_PACK_SOURCE` explícitamente; registrar `release_status`, `source_commit` y estado Git. Previsualizar:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
```

La versión anterior es solo procedencia. Clasificar el contenido como `absent`, `managed`, `locally_modified`, `unmanaged`, `obsolete`, `conflict` o `already_aligned`. Hacer converger el contenido gestionado reconocido, reducir el bloque SR de `AGENTS.md` y preservar código, secretos, dependencias, estado de producto, historial y skills locales. Eliminar obsoletos solo con huella reconocida. Reconciliar el perfil por capacidad; añadir `MCP_POLICY.yaml` y `task_state.yaml`; mantener legibles los contratos antiguos.

Informar plan, conflictos y preservaciones, y esperar autorización exacta. Después:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --upgrade
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

No cerrar lotes ni ejecutar build, despliegue, migración o llamada MCP. El post-check debe probar `4.1.0`, rutas, documentación, skills y preservación. Las etiquetas legacy `managed_update`, `already_current` y `reconciliation_required` siguen legibles; ninguna rama depende de una versión como `2.2.0`. Después usar `06_verify_sr_installation.md` y, solo si hace falta, `07_realign_sr_state_after_upgrade.md`.
