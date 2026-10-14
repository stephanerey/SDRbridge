# SR-4.1-Lots definieren

Nicht programmieren. Lies die geltende `AGENTS.md`, die relevante Anforderung und eine vorhandene `SR_LOTS.yaml`; prüfe nur notwendige Produktdateien.

Trenne neue Fähigkeit und Reparatur. `existing_requirement_repair` öffnet das Lot erneut; `validated_requests` bleibt ein Kompatibilitätsfeld. Schlage möglichst wenige kohärente Lots mit Ziel, `Scope`, beobachtbaren Kriterien, Abhängigkeiten, `Verification`, getrennter `Activation`, Entscheidungen und Stoppbedingungen vor.

Kein eigenes Dokumentations-Gate. Die Kernmethode hat keine MCP-Abhängigkeit; externe Fähigkeiten folgen `MCP_POLICY.yaml`. Nutze `task_state.yaml` nur für nützliche Kontinuität und validiere den Vertrag.
