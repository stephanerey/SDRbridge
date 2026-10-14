# Décisions et paramètres — suivi v0.3

## Résolution pour le lancement

Le complément [S6](../specs/06_IMPLEMENTATION_BASELINE.md) fixe les defaults que le prompt de lancement retient : P-02..14 conservés, P-01 Python3.12 isolé. O-01 reste V1 mono-source ; O-03/O-04/O-09/O-10 sont tranchées techniquement dans S6, avec mesures à produire. O-02 : inventaire effectué, capacités RSPdx encore à mesurer. O-05 : SDR++ raw UDP choisi, ANTRACK isolé, QMAP différé. O-06 : loopback pour développement, LAN désactivé jusqu'à autorisation. O-07 : import/Git réalisés, publication non autorisée. O-08 : backend natif conservé. O-11 reste ouvert uniquement pour l'essai Nexus facultatif.

Le registre ci-dessous conserve les questions de la v0.2 pour traçabilité ; ses mentions d'absence d'import/installation décrivent l'état antérieur, pas l'état courant.

Date : 13 octobre 2026. Les acquis proviennent de la discovery puis de sa reprise. Les valeurs nouvelles sont des propositions techniques explicites, applicables après validation du lot qui les utilise. Elles évitent que chaque exécution invente un comportement différent.

## Acquis

A-01 : RX uniquement. A-02 : une source matérielle active en V1, architecture extensible. A-03 : clients sans autorité matérielle. A-04 : PyQt5/PyQtGraph et headless. A-05 : Soapy principal. A-06 : pas de plafond fixe de quatre clients. A-07 : DSP mutualisé et filtré. A-08 : DDC hors V1. A-09 : LAN/VPN. A-10 : compact monitor. A-11 : record/replay cible SigMF. A-12 : SR 4.1.0, Nexus évalué en parallèle.

## Paramètres proposés pour les lots

| ID | Choix proposé | Motif / portée |
|---|---|---|
| P-01 | Windows 11 Pro confirmé ; Python 3.11 minimum hérité pour le bridge ; versions exactes des dépendances fixées après audit | Préserver l'écosystème existant ; environnement ANTRACK distinct si nécessaire |
| P-02 | Source active unique : matériel OU replay OU simulation | Rendre la limite V1 testable tout en préparant des sessions indépendantes |
| P-03 | Reconfiguration RF par commande sérialisée avec révision attendue | Empêcher l'application de réglages concurrents ou issus d'un écran ancien |
| P-04 | Plages RF semi-ouvertes, priorités explicites, égalité ambiguë rejetée | Comportement déterministe aux frontières |
| P-05 | Profils de sortie immuables ; édition = nouvelle version | Ne pas altérer silencieusement un pipeline partagé |
| P-06 | Heartbeat natif 5 s, expiration 15 s ; surveillance données 2 s ; reprises après 1, 2, 5, 10, 30 s, puis arrêt | Valeurs initiales configurables et testables, pas exigences matérielles universelles |
| P-07 | Paquet UDP natif : budget applicatif 1 200 octets, header v2 de 72 octets | Limiter les fragments et documenter chaque champ ; adaptation VPN possible |
| P-08 | Contrôle historique sur loopback 47631 ; nouveau contrôle natif 47632 désactivé par défaut | Isoler la compatibilité historique du nouveau protocole |
| P-09 | CS16 et CF32 comme formats natifs initiaux ; aucune DDC, offset non nul rejeté | Réduire la surface du premier DSP |
| P-10 | Gabarit FIR : bande utile ±0,40 Fs_sortie, bande rejetée dès ±0,50 Fs_sortie, ondulation ≤0,1 dB, réjection ≥80 dB | Proposition à mesurer en flottant ; qualité sur CS16 vérifiée séparément |
| P-11 | GUI : cadence spectre plafonnée à 15 Hz, statistiques 1 Hz ; cible compact 480×120 pixels logiques, minimum 360×100 | Paramètres d'affichage initiaux, ajustables sans modifier la réception |
| P-12 | Nouveau contrôle LAN natif avec jeton de lecture ; destinataire unicast client limité à son adresse pair | Ne pas fournir une émission arbitraire à un client distant |
| P-13 | Files bornées ; surcharge d'un consommateur = pertes comptées chez lui | Aucun client lent ne bloque la source |
| P-14 | Arrêt de recorder sur saturation/disque plein ; pas d'effacement automatique d'anciens fichiers | Préserver la réception et les captures existantes |

Les tests qui utilisent une minuterie doivent employer une horloge injectable lorsque possible ; ne pas faire attendre les tests unitaires en temps réel pendant les délais du tableau.

## Questions réellement ouvertes

| ID historique | Question | Action possible avant réponse | Blocage ciblé |
|---|---|---|---|
| O-01 | Multi-SDR simultané dès la première livraison ? | Continuer avec A-02 ; contrats compatibles | Changement du périmètre V1 seulement |
| O-02 | RSPdx et Windows 11 Pro confirmés ; pilotes, capacités/canaux exposés et machine à relever | Sources simulées et tests de contrat | Qualification RF matérielle et packaging |
| O-03 | Valider les règles RF détaillées ? | Contrat P-04 proposé | Lot RF avant comportement utilisateur définitif |
| O-04 | Gabarit DSP et budgets de performance finaux ? | Caractériser P-10 en simulation | Engagement de qualité/performance final |
| O-05 | HDSDR 2.81a et SDR++ 1.2.1 confirmés ; ANTRACK main repéré ; interfaces et QMAP à préciser | Préserver l'amont, client natif de référence | Adaptateurs tiers et leur recette |
| O-06 | Interfaces réseau et politique d'accès locale réelles ? | Implémentation désactivée par défaut selon P-08/P-12 après validation du lot | Activation LAN/VPN |
| O-07 | Import de l'amont, initialisation Git et politique de publication autorisés ? | Documents dans le dossier désigné | Import applicatif, branches, commits et push |
| O-08 | Backend SDRplay natif conservé comme option durable ? | Conserver son comportement tant qu'il n'est pas remplacé | Suppression/changement de support |
| O-09 | Formats/version SigMF, découpage et durée de capture à garantir ? | Modèle de recorder et tests de panne | Finalisation du format externe et qualification disque |
| O-10 | Valider routage/édition/presets détaillés ? | Proposition S1/S5 | Livraison de ces parcours |
| O-11 | URL, authentification et outils MCP Nexus ? | Travail local SR Core | Essai Nexus seulement |

O-07 est partiellement résolue : dépôt distant `stephanerey/SDRbridge`, dossier local `E:/PLDesign/SDRbridge`. L'autorisation de cette tâche couvre la préparation documentaire ; Git et l'import applicatif ne sont pas engagés.

Réponse de Stéphane reçue pendant la préparation : RSPdx connecté, Windows 11 Pro, HDSDR 2.81a et SDR++ 1.2.1 installés ; utiliser le dernier ANTRACK du dépôt. Le dernier `main` observé d'ANTRACK est épinglé au commit `35f1c35b45d0a6a000b93d1d47fb47b6543aefcf`, version déclarée 2.1.0. Son manifeste exige Python 3.9 alors que son README recommande 3.12 : voir [la référence ANTRACK](../reference/ANTRACK_BASELINE.md). Cette divergence bloque l'installation supposée, pas la documentation ni les tests simulés du bridge.
