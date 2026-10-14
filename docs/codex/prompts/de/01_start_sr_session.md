# Eine SR-Sitzung fortsetzen

Vor Scope-Freigabe nicht programmieren. `AGENTS.md`, `CURRENT_STATE` und dann das Ergebnis `selected` von `find_next_session_prompt.py --root . --json` lesen; bei `ambiguous` den genauen Pfad erfragen. Aktives `task_state.yaml` oder nur notwendige historische Vertraege einschliesslich offener `validated_requests` lesen.

Implementierung, Nachweise und menschliche Abnahme trennen: unvollstaendige Implementierung ist `repair`; `user_testing` setzt technisch vollstaendige Arbeit voraus. Einen kohärenten naechsten Scope, seine Pruefung und die benoetigte Freigabe vorschlagen. Fuer Feedback zu einer bestehenden Anforderung kein Mikro-Lot anlegen. `NEXT_SESSION_PROMPT.md` und `procedures/resume.md` nur bei echtem Fortsetzungsbedarf laden.
