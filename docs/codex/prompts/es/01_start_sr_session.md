# Reanudar una sesión SR

No programar antes de validar el alcance. Leer `AGENTS.md`, `CURRENT_STATE` y el resultado `selected` de `find_next_session_prompt.py --root . --json`; si es `ambiguous`, pedir la ruta exacta. Leer el `task_state.yaml` activo o solo los contratos históricos necesarios, incluidas las `validated_requests` abiertas.

Separar implementación, pruebas y aceptación humana: una implementación incompleta es `repair`; `user_testing` exige trabajo técnico completo. Proponer un único alcance coherente, su verificación y la autorización requerida. No crear un micro-lote para comentarios sobre un requisito existente. Cargar `NEXT_SESSION_PROMPT.md` y `procedures/resume.md` solo cuando haga falta continuidad.
