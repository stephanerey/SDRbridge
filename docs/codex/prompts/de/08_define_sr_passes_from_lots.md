# SR-4.1-Passes definieren

Nicht programmieren. Lies die geltende `AGENTS.md`, `SR_LOTS.yaml` und eine vorhandene `SR_PASSES.yaml`; öffne Produktdateien oder `task_state.yaml` nur bei echtem Bedarf.

Fasse Lots mit `repair`, `reopened` oder `validated` in möglichst wenige kohärente Passes zusammen. Nenne je Pass Ziel, erlaubten `Scope`, Abhängigkeiten, abschließende `Verification`, getrennte `Activation`, menschliche Entscheidungen und echte Stoppbedingungen.

Erzeuge kein eigenes Dokumentations-Gate. Historische Felder dienen nur der Kompatibilität. Die Kernmethode hat keine MCP-Abhängigkeit; externe Fähigkeiten folgen `MCP_POLICY.yaml`.

Lege den Diff vor, beachte die nötige Freigabe und validiere danach den Vertrag.
