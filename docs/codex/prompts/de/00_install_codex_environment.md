# SR Method 4.1 in einem neuen Projekt installieren

Nicht programmieren. Veroeffentlichte Version `4.1.0` installieren, pruefen und vor Anwendungsarbeit stoppen. Naechstes `AGENTS.md` lesen, `SR_PACK_SOURCE` explizit waehlen und `release_status`, `source_commit` sowie Git-Zustand notieren. Eine Quelle ablehnen, die nicht der erwarteten Release entspricht. Bei vorhandenen SR-Markern `05_upgrade_codex_environment.md` verwenden.

Vorschau ausfuehren, Erstellungen und Erhalt melden, genaue Freigabe abwarten und dann `--write` nutzen:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

Das Ziel enthaelt `SR_LOTS.yaml`, `SR_PASSES.yaml` mit `passes: []`, `MCP_POLICY.yaml` im Modus `core` und `task_state.yaml`. Keine Lots, Paesse, Anforderungen oder MCP-Faehigkeiten erfinden. Keinen Anwendungscode, Secrets, Migrationen, Abhaengigkeiten oder Deployments aendern. Ablauf: `00 -> 06` oder `05 -> 06 -> 07`.
