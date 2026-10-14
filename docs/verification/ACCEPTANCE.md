# Plan d'acceptation — v0.3

Les valeurs arrêtées dans S6 remplacent les propositions de durée/seuil de la v0.2. Environnement observé : PREPARATION_REPORT. Aucun AC n'est déclaré réussi par la préparation documentaire.

Tous les cas sont **à exécuter**. Aucun succès n'est affirmé. Une preuve contient révision du bridge, paramètres, environnement, commandes/scénario, résultat et emplacement des traces ; la matrice seule n'est pas une preuve.

## Environnement de référence

Confirmé par Stéphane le 13 octobre 2026 : SDRplay RSPdx connecté ; Windows 11 Pro ; HDSDR 2.81a et SDR++ 1.2.1 installés. Versions de l'API SDRplay, du driver Soapy, architectures des exécutables et caractéristiques CPU/RAM/réseau : à relever avant recette matérielle.

ANTRACK : [état repéré du dépôt](../reference/ANTRACK_BASELINE.md). Ne pas installer les dépendances tant que l'incohérence Python de ce dépôt n'est pas résolue pour la version effectivement utilisée. Le bridge et ANTRACK peuvent nécessiter des environnements Python séparés ; leur transport IQ ne doit pas dépendre d'un environnement partagé.

## Cas déterministes et preuve attendue

| ID | Scénario / préparation | Résultat exigé |
|---|---|---|
| AC-01 | Faux backend : deux appareils même modèle, identités différentes ; capacités discrètes puis continues ; aucun appareil | Identification non ambiguë, widgets valides et absence de crash ; compléter ensuite par RSPdx réel |
| AC-02 | 100 cycles simulés open/start/stop/close ; double start ; stop pendant reprise | Une seule acquisition, ressources libérées, pas de thread résiduel ; toute défaillance initiale distincte d'une régression |
| AC-03 | Réglage valide, hors plage, révision périmée, échec partiel du backend ; tentative client de retune | Valeurs effectives exactes, erreur stable, nouvelle époque si changement appliqué, autorité inchangée |
| AC-04 | Règles [100,200), [200,300) avec fréquences 199/200 ; chevauchement à priorité égale ; suspension manuelle | Choix déterministe, ambiguïté refusée, suspension maintenue jusqu'à réactivation |
| AC-05 | Blocs connus, trou de 4096 complexes, trou inconnu, retune, changement d'horloge simulé | Index/unités corrects, pertes connues distinctes d'inconnues, époque nouvelle quand requise, aucun temps matériel fabriqué |
| AC-06 | 5 lecteurs, dont 1 retardé au-delà de la profondeur du ring ; writer en wrap pendant copie ; départ d'un lecteur | Lecteurs sains continus, pertes du lent comptées, aucun bloc déchiré accepté ; mémoire conforme aux bornes |
| AC-07 | Deux profils équivalents même source, puis deux source_id synthétiques distincts ; suppression d'abonnements | Un pipeline dans le premier cas, deux dans le second ; dernier abonné seul déclenche sa fermeture ; ne prouve pas le multi-SDR réel |
| AC-08 | Formats S3 et resampling 2M→192k/96k ; blocs réguliers puis irréguliers ; tonalités hors bande | Conversion exacte aux bornes ; gabarit FIR mesuré ; pas de dérive ; découpage sans effet hors tolérance documentée |
| AC-09 | Hello valide/invalide, version inconnue, token absent, ligne >64KiB, expiration, unsubscribe, adresse manuelle | Réponses bornées, pas de fuite de jeton, abonnement limité au pair autorisé ; libération des sessions ; aucun contrôle RF |
| AC-10 | Encodeur/parseur indépendants, vecteurs header v2, 2 unicast + multicast, paquets perdus/réordonnés/tronqués | Taille/champs corrects, jamais d'échantillon coupé, pertes détectables ; échec d'une destination isolé |
| AC-11 | Modes normal/compact, 100 bascules, redimensionnement, DPI 100/150/200 %, écran secondaire retiré | Source/abonnements inchangés, pas de seconde FFT par mode, commandes lisibles, fenêtre récupérable, interruption signalée |
| AC-12 | Preset valide/incompatible/corrompu, stockage en échec, auto-start, headless puis Ctrl+C | Aucune substitution de SDR ni perte de config valide ; état partiel annoncé ; sortie et libération cohérentes |
| AC-13 | Pas de données, exception, reconnexion réussie à tentative 3 puis échec total ; Stop pendant attente | Délais testés par horloge injectable, 5 tentatives max, annulation immédiate de la planification ; nouvelle époque après reprise |
| AC-14 | Profil de charge de référence, 10 min fonctionnelles puis 60 min d'endurance simulée ; 60 min réelles après autorisation | Mesures CPU/RAM/débits/pertes/latence comparées aux seuils S6 §7 ; pas seulement « le test a tourné » |
| AC-15 | Capture puis replay, disque plein simulé, changement de taux, EOF/seek, fichier tronqué | Métadonnées validées par format choisi, continuité expliquée, fichier incomplet signalé, réception indépendante préservée |
| AC-16 | ANTRACK au commit retenu + HDSDR 2.81a simultanés sur le RSPdx | Acquisition et mesure ANTRACK correctes, HDSDR reçoit, aucun client ne retune ; gains/débits/qualité documentés |
| AC-17 | SDR++ 1.2.1 Network Source raw CS16 ; QMAP explicitement différé hors verdict V1 | Réception réelle par le module ciblé ; protocole exact publié ; aucune conformité déduite du client Python natif |

Les nombres de répétitions et durées sont des propositions de qualification. Pour le développement, exécuter d'abord les tests ciblés peu coûteux ; ne pas relancer l'endurance à chaque correction documentaire ou locale.

## Mesures et seuils

Profil simulé initial : 2 MS/s CS16, ring 64×4096, cinq lecteurs, sorties 192/96 kS/s et deux unicast natifs. Injecter des données déterministes à cadence contrôlée. Zéro perte inexpliquée sur le scénario nominal est une cible proposée ; un OS non temps réel ne justifie pas de masquer une perte.

Avant AC-14 réel, remplir : CPU/RAM machine, interface et débit réseau, SDR/pilote, durée, formats, profils, nombre de consommateurs, maximum RAM/CPU, pertes tolérées et latence visée. Tant que ces seuils sont absents, le résultat est une caractérisation, pas une qualification réussie.

Latence : identifier émission/capture/réception et domaines d'horloge ; si les horloges ne sont pas comparables, ne pas annoncer une mesure de bout en bout. Présenter médiane et percentile 95 si mesurables. Conserver les données brutes hors des documents de reprise.

Le temps total du run, le nombre de blocs/échantillons et les erreurs de chaque couche sont présents dans le rapport. Les métriques déclarées par un client sont marquées comme telles. La GUI n'est pas un instrument de preuve des pertes réseau à réception.

## Conditions d'acceptation

Pour chaque exigence : implémentation complète + preuves applicables. Si le code manque, statut travail en cours/bloqué, pas simple attente de test utilisateur. Si seule la recette matérielle ou humaine reste, indiquer exactement son scénario et l'environnement manquant.

La qualification ne couvre que les versions testées. Un simulateur ne qualifie pas le pilote SDRplay ; une capture d'écran ne qualifie pas la continuité DSP ; un parseur natif ne qualifie pas TIMF2. Une activation ou publication réelle reste une action distincte des tests locaux.
