# Eine SR-4.1-Installation pruefen

Modus `read_only`. Keine Datei aendern, installieren, restaurieren oder reparieren.

```bash
python3 scripts/codex/verify_codex_pack.py
python3 scripts/codex/validate_release_docs.py --root . --json
python3 scripts/codex/audit_codex_pack.py --root . --json
python3 scripts/codex/sr_post_install_check.py --root . --json
```

`4.1.0`, `AGENTS.md`, Routen, `MCP_POLICY.yaml`, `task_state.yaml`, Lots, Paesse, lokalisierte Dokumentation und Erhalt pruefen. SR Contract 3.1.0, 3.0.0-Vertraege und `audit_sr_task_contracts.py` bleiben legacy-lesbar. Nachweise, Warnungen, Konflikte und Grenzen melden, dann ohne Reparatur stoppen.
