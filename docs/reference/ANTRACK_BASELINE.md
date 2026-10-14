# ANTRACK — cible de compatibilité repérée

Vérification GitHub le 13 octobre 2026. Dépôt identifié : [stephanerey/Antrack](https://github.com/stephanerey/Antrack).

Stéphane demande d'utiliser la dernière version du dépôt. Aucun objet GitHub Release n'a été retourné par l'API. La référence de travail proposée est donc l'état courant de la branche par défaut `main`, épinglé au commit `35f1c35b45d0a6a000b93d1d47fb47b6543aefcf`, daté du 6 août 2026, message « Release Antrack 2.1.0 ». Le manifeste à cette révision déclare `2.1.0`.

Les tags ne permettent pas de choisir simplement le numéro le plus élevé : le tag `2.11` pointe sur `39be360f7639f6ccdd9154cf186d93022ea6becb`, daté du 20 janvier 2026, donc antérieur au `main` observé. Le tag `2.1.0` pointe sur `4532c920015a1d6c79b4a8700211ff7841f9a50f`, également en janvier, et son manifeste porte encore `2.01`. Utiliser la révision plutôt qu'une seule étiquette ambiguë.

## Incohérence à résoudre avant installation

À la révision retenue :

- [pyproject.toml](https://github.com/stephanerey/Antrack/blob/35f1c35b45d0a6a000b93d1d47fb47b6543aefcf/pyproject.toml) exige Python `>=3.9,<3.10` et mentionne les prérequis Windows PothosSDR `2021.07.25-vc16-x64`, SoapySDR `0.8.1`, SDRplay API `3.15`.
- [README.md](https://github.com/stephanerey/Antrack/blob/35f1c35b45d0a6a000b93d1d47fb47b6543aefcf/README.md) recommande Python `3.12.x`.

Ces informations ne démontrent pas ce qui est installé sur le PC. Ne pas modifier ANTRACK pour résoudre cette incohérence dans un lot SDRbridge, ni imposer la même version Python aux deux applications. Inspecter le lanceur/environnement réellement utilisé et les contraintes de l'adaptateur avant décision.

Le lot de compatibilité doit repérer dans cette révision les appels Soapy/lecture IQ effectivement employés, les formats et débits attendus, les hypothèses de réglage matériel et les résultats de mesure à préserver. Cette lecture détaillée et les essais n'ont pas encore été effectués.
