# Runtime-Agenten definieren

Nicht programmieren oder aktivieren. Lies nur notwendige Produkt-, Sicherheits- und Datenverträge. Bevorzuge einen Agenten mit Routing; trenne nur wirklich verschiedene Verantwortungen oder Berechtigungen.

Definiere je Agent Zweck, Eingaben, `output schema`, Berechtigungen, Nebenwirkungen, menschliche Freigabe, `invalid_output_policy` und `Verification`. Nutze Pydantic für strukturierte Python-Ausgaben oder einen gleichwertigen typisierten Validator.

MCP-Fähigkeiten bleiben `deferred`, allowlist-basiert und durch `MCP_POLICY.yaml` begrenzt. Trenne Entwurf, Implementierung und `Activation`; hole danach die Freigabe für den minimalen Vorschlag ein.
