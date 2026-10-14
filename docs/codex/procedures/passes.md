# Multi-lot passes

A pass is the smallest coherent group of validated lots that can be executed without another product decision.

Before execution, confirm order, dependencies, allowed scope, external effects and final verification. Then execute the whole pass without micro-gates while those facts remain unchanged.

Stop only for a new human decision, unsafe mutation, threatened persistent data, unresolved dependency, failed activation or exhausted context requiring a handoff.
