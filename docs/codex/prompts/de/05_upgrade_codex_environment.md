# Eine SR-Installation auf 4.1 aktualisieren

Nicht programmieren. Eine alte, partielle, unbekannte oder angepasste Installation auf die veroeffentlichte Version `4.1.0` konvergieren, ohne das Projekt zu ueberschreiben.

Naechstes `AGENTS.md`, SR-Marker, Zustand, Lots, Paesse und aktive Memory lesen. `SR_PACK_SOURCE` explizit waehlen; `release_status`, `source_commit` und Git-Zustand notieren. Vorschau:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
```

Die vorherige Version ist nur Herkunft. Inhalte als `absent`, `managed`, `locally_modified`, `unmanaged`, `obsolete`, `conflict` oder `already_aligned` klassifizieren. Erkannten verwalteten Inhalt konvergieren, den SR-Block in `AGENTS.md` kuerzen und Anwendungscode, Secrets, Abhaengigkeiten, Produktzustand, Historie und lokale Skills erhalten. Veraltete Artefakte nur bei bekannter Signatur loeschen. Profil nach Faehigkeiten abgleichen, `MCP_POLICY.yaml` und `task_state.yaml` hinzufuegen, alte Vertraege lesbar halten.

Plan, Konflikte und Erhalt melden, dann genaue Freigabe abwarten. Danach:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --upgrade
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

Kein Lot schliessen und keinen Build, Deployment, Migration oder MCP-Aufruf starten. Der Post-Check muss `4.1.0`, Routen, Dokumentation, Skills und Erhalt beweisen. Legacy-Bezeichnungen `managed_update`, `already_current` und `reconciliation_required` bleiben lesbar; keine Verzweigung haengt von einer Version wie `2.2.0` ab. Danach `06_verify_sr_installation.md` und nur bei Bedarf `07_realign_sr_state_after_upgrade.md`.
