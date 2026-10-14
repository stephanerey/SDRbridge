# Realinear el estado SR tras una actualización

Empezar en solo lectura. Leer `AGENTS.md`, `SR_BOOTSTRAP.md`, `CURRENT_STATE`, registros y el resultado `selected` de `find_next_session_prompt.py`; si es `ambiguous`, pedir la ruta y usar `--prompt`.

Leer `task_state.yaml` activo o los contratos legacy necesarios. Inventariar requisitos abiertos, incluidas `validated_requests`, con implementación, pruebas y aceptación. Proponer la mínima realineación y estados `repair`, `user_testing` o `blocked`.

Esperar la validación exacta `je valide` antes de modificar. Después cambiar solo memoria y registros nombrados, nunca código de aplicación. Actualizar `CURRENT_STATE.md` solo con pruebas. No elegir una reanudación por fecha, convertir el historial en masa ni crear un micro-lote para un requisito existente.
