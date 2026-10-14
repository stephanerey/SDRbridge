---
name: aurora-lot-runner
description: >-
  Execute a validated multi-lot pass, a long resume, or a bounded autonomous phase.
---

# SR lot runner

1. Read the compact current state and only the files referenced by the selected pass.
2. Confirm scope, dependencies, authority and final verification before mutation.
3. Execute validated lots without intermediate approval while scope and safety remain unchanged.
4. Keep one compact task state. Do not create intentional failures or duplicate contracts.
5. Stop only for a real scope, safety, dependency, data, activation or human-decision boundary.
6. Close with final evidence, remaining limits and the next executable state.
