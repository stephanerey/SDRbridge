# Resume an SR session

Do not code before scope validation. Read `AGENTS.md`, `CURRENT_STATE`, then the `selected` result from `find_next_session_prompt.py --root . --json`; if it is `ambiguous`, ask for the exact path. Read active `task_state.yaml` or necessary historical contracts, including open `validated_requests`.

Separate implementation, evidence, and human acceptance: incomplete implementation is `repair`; `user_testing` requires technically complete work. Propose one coherent next scope, its verification, and required authority. Do not create a micro-lot for feedback on an existing requirement. Load `NEXT_SESSION_PROMPT.md` and `procedures/resume.md` only when continuity requires them.
