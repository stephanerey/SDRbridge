# Risques et traitement
| Risque | Traitement | Preuve |
|---|---|---|
| Bloc déchiré, pointeur périmé | Ring v2 aligné + helper natif + copie vérifiée | Stress multiprocessus x64/Win32 AC-06 |
| Alias et frontières de blocs | FIR polyphase avec état/oracle | AC-08 et partitionnement aléatoire |
| Retune mal étiqueté | Commandes sérialisées, arrêt/reprise si frontière inconnue | AC-03/05 |
| Client lent ou disque plein | Files bornées, isolation, compteur explicite | AC-06/10/15 |
| Accès LAN abusif | Jeton, destinations limitées, quotas, désactivé par défaut | AC-09 |
| ABI Python/Soapy/ExtIO | Environnements isolés, builds deux architectures | AC-01/16/17 |
| Compatibilité déclarée sans essai | Matrice séparant simulé, compilé et matériel réel | QUAL |
| Licence/distribution incertaine | Vérifier sources et licences de dépendances avant emballage/publication | QUAL ; aucun push automatique |
