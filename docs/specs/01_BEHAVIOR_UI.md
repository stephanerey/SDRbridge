# S1 — Comportements, RF et interface

Statut : contrat fonctionnel proposé v0.2. Acquis et valeurs proposées : [DECISIONS](../product/DECISIONS.md). Couverture : REQ-001 à REQ-007, REQ-019, REQ-024 à REQ-029. Tests : [ACCEPTANCE](../verification/ACCEPTANCE.md).

## 1. Cycle de vie et commandes

La source active suit les états suivants ; l'interface les traduit en français. Toute commande retourne un résultat explicite et l'état effectif, sans annoncer un succès avant application.

| État | Entrée | Commandes disponibles | Sortie normale |
|---|---|---|---|
| IDLE | Aucun appareil ouvert | Découvrir, sélectionner, ouvrir, sélectionner simulation/replay | OPENING |
| OPENING | Commande d'ouverture en cours | Annuler si supporté ; sinon attendre résultat | READY ou ERROR |
| READY | Source ouverte, réception arrêtée | Régler, démarrer, fermer | STARTING ou IDLE |
| STARTING | Validation et démarrage du flux | Pas de seconde commande start ; stop mis en attente | RUNNING ou ERROR |
| RUNNING | Blocs reçus | Régler, arrêter, gérer abonnements et recorder | RECONFIGURING, STOPPING ou RECOVERING |
| RECONFIGURING | Modification sérialisée du matériel | Commandes RF désactivées ; stop prioritaire à la prochaine frontière sûre | RUNNING ou ERROR |
| STOPPING | Arrêt en cours | Pas de nouveau start | READY, IDLE si close demandé, ou ERROR |
| RECOVERING | Source perdue ou watchdog déclenché | Annuler reprise, arrêter | RUNNING après réouverture ou ERROR |
| ERROR | Échec documenté, réception non garantie | Lire diagnostic, réessayer, fermer | OPENING ou IDLE |

Toutes les commandes RF passent par le contrôleur et une file sérialisée. Un double-clic Start ne crée pas deux threads d'acquisition. Stop annule les reprises planifiées. Un échec de fermeture reste visible ; ne pas effacer l'erreur en affichant artificiellement IDLE.

Au démarrage RX, créer une époque de flux. Tout redémarrage, perte de continuité ou changement de configuration effectif crée une nouvelle époque selon S2. Pendant une reconfiguration, aucun bloc ne porte les paramètres nouveaux tant qu'ils ne sont pas appliqués. Si le backend ne permet pas de déterminer la frontière, arrêter/reprendre l'acquisition plutôt que mal étiqueter des données.

Quitter la GUI en mode application interactive demande confirmation seulement si RX ou enregistrement est actif : « Arrêter la réception et quitter » / « Annuler ». Réduire et passer en compact ne ferment pas la source. Détacher la GUI d'un service persistant est hors V1.

## 2. Appareils et contrôles matériels

L'écran Device présente modèle, backend, identifiant stable disponible, état et message de diagnostic. Une redécouverte ne sélectionne pas automatiquement un autre appareil. Si aucun identifiant stable n'existe, désactiver la reconnexion automatique à une identité ambiguë et expliquer pourquoi.

Les contrôles sont générés à partir des capacités :

| Capacité | Widget et validation |
|---|---|
| Fréquence | Entrée décimale avec unité Hz/kHz/MHz, valeur interne entière en Hz ; plages supportées affichées |
| Taux d'échantillonnage / bande passante | Liste quand valeurs discrètes, entrée contrainte quand plage continue ; aucune valeur inventée |
| Antenne / horloge | Liste des identifiants réels, libellé lisible si disponible |
| Gain par étage | Un contrôle par nom exposé ; unité et bornes du driver ; ne pas assimiler systématiquement gain et atténuation |
| AGC | Disponible uniquement si exposée ; gains manuels concernés désactivés tant que l'AGC les pilote |
| Réglage spécifique | Booléen, enum, entier, flottant ou texte selon métadonnées ; champ inconnu avancé, jamais bouton arbitraire |

Le formulaire distingue brouillon et appliqué. « Appliquer » soumet les seuls changements avec `expected_config_revision`. Une révision périmée renvoie `STALE_CONFIG` et recharge les valeurs effectives avant une nouvelle action opérateur. Une entrée invalide conserve le brouillon et montre la raison près du champ.

Après application, relire le matériel lorsque le backend le permet. Une valeur ajustée est affichée comme telle. Sans readback, afficher « appliqué, non relu » ; ne pas la qualifier de mesure. Si la troisième d'une série de modifications échoue, relire tous les paramètres concernés et montrer l'état partiel réel. Ne pas prétendre qu'une transaction matérielle est atomique.

Le contrôleur refuse une demande TX et les commandes matérielles provenant d'un client IQ. La compatibilité avec un ancien client qui envoie ces commandes est documentée par son adaptateur, sans lui donner de nouveaux droits.

## 3. Profils RF

Une règle comporte `rule_id`, plage `[min_hz, max_hz)`, priorité entière, état activé et paramètres RF nommés. Les fréquences sont celles demandées et validées pour la source. Une règle ne change pas elle-même la fréquence.

À fréquence donnée, parmi les règles activées applicables au matériel sélectionné, choisir la priorité la plus élevée. Refuser à l'enregistrement deux règles de même priorité qui se recouvrent pour ce matériel. Aucun cumul implicite de gains provenant de plusieurs règles. Si aucune règle ne correspond, conserver les réglages RF actuels et afficher « aucune règle applicable ».

Une fréquence exactement à la borne haute appartient à la règle suivante éventuelle, pas à la précédente. Le contrôle valide les paramètres de la règle contre les capacités avant application ; si une règle obligatoire est incompatible, refuser le changement de fréquence associé et afficher les champs fautifs. Ne pas retuner puis ignorer silencieusement une atténuation requise.

Mode « automatique » : un changement de fréquence applique la règle pertinente. Une modification manuelle d'un paramètre piloté passe le profil en « suspension manuelle » ; la radio conserve cette dérogation jusqu'à « Réactiver le profil ». Changer la fréquence pendant suspension ne réactive pas implicitement le profil. Ces choix sont proposés par P-04/O-03.

## 4. Écrans normaux et actions

La barre commune contient source, état RX, fréquence effective, Start/Stop, état recorder et compteur d'alertes. Les unités restent visibles ; l'état ne repose jamais sur une couleur seule.

| Écran | Contenu minimal | Actions et résultat |
|---|---|---|
| Device | Inventaire, capacités, brouillon RF, valeurs appliquées | Redécouvrir, ouvrir/fermer, appliquer ; comportement du §2 |
| Spectrum | Spectre, waterfall, fréquence centrale et échelle relative | Zoom/échelle modifient l'affichage seulement ; un geste de retune doit être explicite et passer par le contrôleur |
| RF Profiles | Règles, plage, priorité, matériel, mode auto/suspendu | Créer/éditer/désactiver ; valider les recouvrements avant sauvegarde |
| Streams & Clients | Sources, profils, abonnements, destinations, états et métriques | Ajouter destination, abonner, arrêter sortie ; aucun changement matériel implicite |
| Network | Interfaces, ports, uni/multicast, état écoute | Activer explicitement une interface ; erreur de bind lisible ; pas de modification automatique du pare-feu |
| Recorder | Flux choisi, chemin, octets, temps, espace restant | Démarrer/arrêter ; gérer les pannes selon S5 |
| Diagnostics | État, pertes par couche, journaux et versions | Export de diagnostic sans secrets ; réinitialisation des compteurs affichés sans modifier les compteurs de protocole |

Table clients : nom déclaré, version déclarée, adresse/transport, dernière présence, profil, source, débit émis et éventuellement reçu déclaré. Table destinations : adresse, profil, état d'émission, débit. Un émetteur UDP configuré sans retour client est « émission active — réception non confirmée », jamais « client connecté ».

Créer un profil de sortie demande un nom, un taux, un format et un protocole. L'offset est affiché à zéro et non éditable en V1. Une demande externe non nulle est rejetée. Un profil utilisé ne se modifie pas en place : créer sa nouvelle version, présenter les abonnements à migrer, puis effectuer une bascule explicitement confirmée. En cas d'échec de création du nouveau pipeline, conserver les abonnements précédents.

Arrêter une destination ne ferme ni le SDR ni les autres abonnements. Supprimer un profil utilisé exige d'abord de fermer ou migrer ses abonnements, avec une liste visible. La matrice multi-SDR reste hors V1 ; l'interface affiche néanmoins l'identité de source au lieu d'un nom global implicite.

## 5. Compact Monitor et réactivité

Contenu : fréquence effective, nom court de source, indicateur RX texte/couleur, mini-spectre et accès au mode normal. Le compteur de clients représente uniquement les sessions confirmées ; afficher les destinations séparément si elles sont montrées.

Taille initiale proposée 480×120 pixels logiques, minimum 360×100. Toujours au premier plan : option mémorisée. Position et taille sont restaurées dans la zone visible d'un écran présent ; après déconnexion d'un écran, ramener la fenêtre sur l'écran principal.

La bascule normal/compact ne redémarre pas la source, ne recrée pas les abonnements et n'instancie pas une deuxième FFT pour le même affichage. Les vues consomment le dernier résultat d'un service de spectre partagé. Cadence plafonnée à 15 Hz ; statistiques 1 Hz. Le waterfall peut cesser son dessin lorsque masqué.

La GUI ne travaille pas dans le callback matériel. L'affichage privilégie la dernière image disponible et abandonne les images anciennes plutôt que d'accumuler une file. Toute modification des widgets reste sur le thread Qt approprié.

En absence de nouveaux échantillons depuis le délai de surveillance, griser le spectre, indiquer « flux interrompu » et ne pas présenter la dernière trace comme une réception en cours. Ne pas confondre silence RF et absence d'échantillons.

Vérification native requise : 100 %, 150 % et 200 % de mise à l'échelle Windows, petit et grand écran, texte lisible, focus clavier, champs invalides et bascule pendant RX. Des captures seules ne démontrent pas la continuité des données.
