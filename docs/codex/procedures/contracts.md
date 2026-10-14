# Legacy contract compatibility

V4.1 uses `task_state.yaml` for new task continuity. Existing `sr_contract.json`, `loop_contract.json` and their validators remain readable for historical tasks and upgrades.

Do not create both legacy contracts for a new V4.1 task. When importing legacy state, preserve open requirements, evidence status and human-validation needs in the compact task state.
