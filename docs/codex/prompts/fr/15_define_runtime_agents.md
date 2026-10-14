# Définir les agents runtime

Ne code pas et n'active rien. Lis uniquement les contrats produit, sécurité et données nécessaires. Préfère un agent unique ; sépare seulement des responsabilités ou permissions réellement distinctes.

Définis pour chaque agent : objectif, entrées, `output schema`, permissions, effets de bord, validation humaine, `invalid_output_policy` et `Verification`. Utilise Pydantic pour une sortie structurée consommée en Python, ou un validateur typé équivalent.

Les capacités MCP restent `deferred`, allowlistées et bornées par `MCP_POLICY.yaml`. Sépare conception, implémentation et `Activation`, puis demande validation sur une proposition minimale.
