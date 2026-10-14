# Pass Runtime Goal

- generated_at:
- pass_id:
- pass_status:
- source_passes: `docs/codex/SR_PASSES.yaml`
- source_lots: `docs/codex/SR_LOTS.yaml`
- max_goal_command_chars: 1000
- hard_limit: 4000
- goal_command_chars:

## Goal Command

```text
/goal Executer PASS-ID selon docs/codex/tasks/YYYY-MM-DD_pass-id/pass_runtime_goal.md. Stopper uniquement sur les stop conditions SR. Ne pas declarer termine avant Pass Completion Gate.
```

## Objective

Executer la passe SR validee jusqu'a son statut final correct. Ce fichier est un artefact runtime derive; il ne remplace jamais `SR_PASSES.yaml`, `SR_LOTS.yaml` ou les `sr_contract.json`.

## Execution Order

1. `LOT-ID`

## E2E Strategy

- mode: grouped_at_pass_end
- items:

Si `grouped_at_pass_end`, Codex ne demande pas d'E2E utilisateur apres chaque lot. Les preuves automatisees sont accumulees par lot, puis une checklist E2E groupee est produite en fin de passe.

## Pass Completion Gate

La passe atteint son statut SR final correct, pas necessairement `done`.

- `done`: tous les gates requis passent et aucune validation/E2E utilisateur ne reste requis.
- `user_testing`: la passe est techniquement prete et attend les E2E ou la validation utilisateur.
- `repair`: une couverture, verification ou exigence reste incomplete mais reparable.
- `blocked`: une stop condition SR bloque la suite.

`done` est interdit si des E2E utilisateur ou une validation humaine restent requis.

## Stop Conditions

- nouvelle validation humaine requise
- dependance invalide ou non satisfaite
- secret, action externe ou migration non disponible/non valide
- risque high/critical non valide
- gate rouge sans reparation defendable
- budget contexte a risque sans prompt de reprise

## Non Regression Rules

- Ne pas elargir ni reduire silencieusement le scope valide.
- Ne pas executer une passe `proposed`.
- Ne pas enchainer une passe suivante sans validation utilisateur explicite.
- Valider `SR_PASSES.yaml` avec `validate_pass_contract.py` avant et apres execution si la passe est utilisee ou modifiee.
