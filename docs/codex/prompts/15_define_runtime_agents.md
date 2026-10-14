# Définir les agents runtime

Ne code pas, ne déploie pas et n'active aucun agent.

Lis le `AGENTS.md` applicable, la méthode IA runtime et uniquement les contrats produit, sécurité et données nécessaires. Pars d'un agent unique avec routage ; sépare plusieurs agents seulement lorsque des responsabilités, permissions ou schémas de sortie réellement distincts le justifient.

Pour chaque agent proposé, définis : objectif borné, entrées, `output schema`, permissions, outils ou actions, effets de bord, validation humaine, politique d'échec et `invalid_output_policy`, ainsi que la `Verification` attendue. Utilise Pydantic lorsque Python consomme une sortie structurée, ou un validateur typé équivalent dans une autre stack.

Les capacités MCP restent `deferred`, allowlistées et bornées par `docs/codex/MCP_POLICY.yaml`. N'invente ni serveur ni nom d'outil. Sépare conception, implémentation, Activation et décision humaine.

Rends la proposition minimale et quelques cas représentatifs. N'écris pas un prompt exhaustif ni une matrice de tests complète avant validation.
