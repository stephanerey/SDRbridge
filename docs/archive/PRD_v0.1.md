# SDR_Bridge — Product Requirements Document

Version : 0.1 — première rédaction pour revue produit  
Date : 13 octobre 2026  
Responsable produit : Stéphane  
Méthode de développement cible : Aurora SR Method 4.1.0

## 1. Statut et lecture du document

Ce document initie le futur Codex Project Pack. La rédaction est autorisée ; elle ne vaut pas validation de tous les détails nouveaux ni lancement de l'implémentation. Aucun développement applicatif, installation SR ou raccordement MCP n'est réalisé par ce document.

Trois niveaux distinguent les décisions :

- **Acquis** : orientation explicitement demandée ou acceptée dans la conversation de discovery et maintenue dans cette reprise.
- **Proposé** : précision de comportement, critère d'acceptation ou découpage introduit dans cette version pour rendre le produit réalisable.
- **Ouvert** : choix ou mesure nécessaire avant le lot concerné ; aucune valeur fictive ne doit être transformée en engagement.

Les orientations du §4 reprennent les décisions historiques. Les détails opérationnels et critères des §6 à §11 constituent une proposition de spécification à relire. Ils ne décrivent pas des fonctionnalités déjà présentes. Les lots du §13 restent proposés.

L'autorisation actuelle porte sur le PRD et l'évaluation Nexus. Le dépôt de développement, les seuils de performance et la qualification matérielle restent à préciser. Les fichiers synchronisés sous `sources/` restent des références en lecture seule.

## 2. Vision et problème à résoudre

SDR_Bridge permet à un opérateur de configurer un récepteur SDR et de distribuer son signal complexe I/Q à plusieurs applications locales ou distantes. Le bridge centralise le matériel et mutualise les traitements identiques, tout en permettant à chaque client de recevoir un flux adapté.

Le produit vise trois usages principaux :

1. Utiliser simultanément plusieurs logiciels sur le même signal, sans leur faire ouvrir chacun le SDR physique.
2. Fournir des flux adaptés en fréquence d'échantillonnage, format et protocole, sur la machine locale ou le réseau.
3. Régler la station dans une interface complète, puis conserver un petit moniteur pendant le travail dans les logiciels clients.

Le succès se mesure par la stabilité de réception, la compatibilité démontrée avec les clients prioritaires, la qualité DSP et la facilité de diagnostic. Un nombre de fonctionnalités ou de connexions affichées ne suffit pas à prouver ces résultats.

## 3. Point de départ et provenance

Base envisagée : [f5jwf/SDR_Bridge](https://github.com/f5jwf/SDR_Bridge), révision observée `7efd536e059e60130884e6aef3a23e1e5aea79dc`, datée du 9 août 2026.

Le [README de cette révision](https://github.com/f5jwf/SDR_Bridge/blob/7efd536e059e60130884e6aef3a23e1e5aea79dc/README.md) décrit une V0.2 Windows utilisant SDRplay, la mémoire partagée, une ExtIO HDSDR et un adaptateur ANTRACK. La sortie réseau est expérimentale. Ces indications sont celles du dépôt ; aucun de ses essais matériels n'a été reproduit pendant la rédaction.

La discovery précédente propose de conserver les briques utiles et de faire évoluer l'architecture. Un audit du code réel devra confirmer ce qui est réutilisable, notamment les interfaces partagées et les dépendances natives. La présente rédaction ne constitue pas cet audit.

Sources de décisions : conversation « Analyse du dépôt SDR », identifiant `6a845f88-fd08-83ed-807f-1121c9d97e2b`, et échanges de reprise du 13 octobre 2026. Le « je valide » suivant les douze propositions de discovery constitue la base des orientations ci-dessous. La proposition ultérieure d'avancer le multi-SDR simultané n'a pas reçu de validation explicite identifiée.

## 4. Orientations acquises

| ID | Décision maintenue | Conséquence |
|---|---|---|
| DEC-001 | RX uniquement | Aucune émission ni activation TX, même si le matériel le permet. |
| DEC-002 | SoapySDR comme interface matérielle principale | Découverte et contrôles issus des capacités réelles ; adaptations matérielles ciblées si nécessaire. |
| DEC-003 | V1 avec un SDR actif à la fois | Plusieurs appareils détectables ; architecture prévue pour plusieurs sessions futures. |
| DEC-004 | Contrôle matériel centralisé | Les clients IQ sont en lecture seule ; un bail de contrôle distant reste hors V1. |
| DEC-005 | GUI PyQt5 / PyQtGraph et fonctionnement headless | Même cœur applicatif, sans dépendance fonctionnelle à une fenêtre ouverte. |
| DEC-006 | Mémoire partagée locale et réseau multi-clients | Pas de limite arbitraire à quatre clients ; bornes de ressources et garde-fous configurables. |
| DEC-007 | Profils de flux et traitement mutualisé | Resampling filtré et conversions partagés lorsque la source et les paramètres sont identiques. |
| DEC-008 | UDP unicast et multicast | Plans de contrôle et de données distincts ; protocole adapté à chaque intégration. |
| DEC-009 | DDC par client hors V1 | Préparer un décalage de fréquence dans les contrats ; refuser une demande non prise en charge. |
| DEC-010 | Accès distant via VPN | Pas d'exposition Internet directe comme scénario V1 pris en charge. |
| DEC-011 | Priorité ANTRACK, HDSDR, SDR++, QMAP, puis clients Python | Ordre de qualification ; aucune compatibilité déclarée sans essai. |
| DEC-012 | Record/replay IQ, cible SigMF | Le replay utilise l'abstraction de source du cœur. |
| DEC-013 | Profils RF, presets complets et redémarrage automatique optionnel | Restaurer une station cohérente, pas seulement sa fréquence. |
| DEC-014 | Reconnexion, watchdog, métriques et simulation | Comportements de panne observables et testables. |
| DEC-015 | Découverte mDNS/Zeroconf avec adresse manuelle | La découverte n'est jamais un prérequis. |
| DEC-016 | Compact Monitor Mode | Petite fenêtre avec fréquence et spectre, bascule sans interruption de réception. |
| DEC-017 | SR Method 4.1.0 pour le futur développement | Référence figée, vérifications adaptées au risque et au logiciel natif. |
| DEC-018 | Évaluation de Nexus en parallèle | Son raccordement ne conditionne pas la rédaction ni le démarrage en mode SR Core. |

Le cœur reste propriétaire du matériel en headless ; « contrôle par la GUI » signifie une autorité opérateur unique, pas une obligation de faire tourner une GUI.

## 5. Périmètre et exclusions

La cible V1 comprend les orientations ci-dessus, livrées progressivement. Une première tranche fonctionnelle mono-SDR peut précéder la V1 complète ; elle ne doit pas être présentée comme couvrant toutes les exigences.

Hors V1 : émission TX, contrôle matériel arbitré entre plusieurs clients, DDC indépendante par client, synchronisation cohérente de plusieurs SDR, accès public Internet natif, GUI de contrôle distante et transformation du bridge en démodulateur universel.

Le multi-SDR simultané avec routage source/client reste une évolution architecturale prévue. Son inclusion dans la première version utilisable est la décision ouverte O-01. La découverte de plusieurs appareils ne prouve pas l'acquisition simultanée ; cette dernière ne prouve pas non plus la cohérence de phase.

Nexus est un outil de développement. L'application distribuée doit fonctionner sans compte Nexus, sans serveur OVH et sans accès au graphe de connaissances.

## 6. Parcours utilisateur proposés

| ID | Parcours | Résultat attendu |
|---|---|---|
| UX-01 | Lancer, détecter les SDR, sélectionner un appareil, régler puis démarrer | Capacités compréhensibles, paramètres effectivement appliqués et état RX visible. |
| UX-02 | Ajouter ANTRACK et HDSDR au signal actif | Les deux reçoivent sans prendre le contrôle du SDR ; leur départ ne coupe pas la source. |
| UX-03 | Créer un profil réseau, choisir la destination et connecter un client | Format, débit et protocole explicites ; erreur lisible si demande impossible. |
| UX-04 | Charger un preset de station | Aperçu des réglages concernés, validation des capacités et signalement d'une configuration partiellement applicable. |
| UX-05 | Passer du mode normal au Compact Monitor puis revenir | Même acquisition et mêmes abonnements ; petit spectre mis à jour sans deuxième chaîne FFT dédiée au mode. |
| UX-06 | Débrancher le SDR ou provoquer une absence de données | État dégradé visible, discontinuité enregistrée et reprise contrôlée sans fausse continuité. |
| UX-07 | Enregistrer, arrêter, puis relire un fichier IQ | Métadonnées interprétables, lecture via le même cœur et fin de fichier gérée explicitement. |
| UX-08 | Démarrer sans écran avec une configuration sauvegardée | Acquisition et distribution opérationnelles ; diagnostic disponible sans widgets Qt. |

## 7. Exigences et critères d'acceptation proposés

Les identifiants REQ sont stables. Les valeurs numériques non encore choisies sont renvoyées aux décisions ouvertes. Une exigence n'est acceptée que lorsque ses preuves applicables sont disponibles.

### 7.1 Acquisition et contrôle RF

| ID | Exigence | Critère observable |
|---|---|---|
| REQ-001 | Détecter et identifier les appareils | Deux appareils de même modèle restent distinguables par une identité disponible et documentée ; absence de matériel affichée sans plantage. |
| REQ-002 | Exposer les capacités réelles | Fréquences, taux, bandes passantes, antennes, gains et options pertinentes proviennent du backend ; option absente non présentée comme utilisable. |
| REQ-003 | Gérer la session RX | Ouverture, démarrage, arrêt et fermeture répétés libèrent correctement les ressources ; aucune voie TX n'est ouverte. |
| REQ-004 | Valider les réglages | Toute valeur hors capacité est refusée ou ajustée avec retour explicite ; l'interface distingue demandé, appliqué et inconnu. |
| REQ-005 | Centraliser l'autorité | Une commande client de fréquence/gain ne modifie pas le SDR ; elle est refusée ou traitée conformément au contrat de compatibilité, avec état effectif cohérent. |
| REQ-006 | Appliquer des profils RF selon la fréquence | Règles de bornes, recouvrement, priorité et dérogation manuelle définies avant implémentation ; changements testés aux frontières des plages. |
| REQ-007 | Gérer les changements pendant RX | Une modification nécessitant un redémarrage est annoncée ; clients et enregistrements identifient la nouvelle configuration et l'éventuel trou. |

### 7.2 Flux, mémoire partagée et DSP

| ID | Exigence | Critère observable |
|---|---|---|
| REQ-008 | Distribuer localement sans plafond fixe de quatre | Au moins cinq lecteurs simulés vérifient la disparition de la restriction ; la capacité garantie reste définie par la campagne de charge. |
| REQ-009 | Isoler les lecteurs lents | Un lecteur en retard perd ses propres données anciennes selon la politique documentée ; il ne bloque ni l'acquisition ni les autres lecteurs. |
| REQ-010 | Mutualiser les traitements identiques | Deux abonnements à une même source et un même profil utilisent une seule chaîne DSP ; le départ d'un abonné ne détruit pas celle encore utilisée. |
| REQ-011 | Effectuer un resampling filtré | Les conversions prioritaires, notamment vers 192 et 96 kS/s, respectent un gabarit de filtre validé ; fréquence utile, alias, gain et compteurs sont mesurés. |
| REQ-012 | Convertir les formats explicitement | Ordre I/Q, type, endianness, normalisation et saturation sont définis et vérifiés avec des vecteurs connus. |
| REQ-013 | Conserver la traçabilité temporelle | Compteurs monotones par époque ; origine/validité des timestamps explicites ; aucune heure hôte présentée comme timestamp matériel. |
| REQ-014 | Décrire les discontinuités | Pertes connues SDR, ring, DSP et réseau séparées ; métrique indisponible affichée comme inconnue, pas comme zéro. |
| REQ-015 | Préparer l'extension multi-SDR | Identités de source explicites, pas de source globale implicite dans les nouveaux contrats ; aucune mutualisation entre appareils indépendants. |

La clé de mutualisation doit inclure la source, son époque/configuration pertinente et les paramètres DSP. Un nom de profil identique sur deux SDR ne rend pas leurs signaux interchangeables. Le paquetage réseau et les destinations peuvent rester distincts après un traitement commun.

### 7.3 Réseau et clients

| ID | Exigence | Critère observable |
|---|---|---|
| REQ-016 | Séparer contrôle et transport IQ | Contrôle TCP/JSON envisagé pour les clients natifs ; données UDP ; fermeture d'une connexion de contrôle traitée selon une politique documentée. |
| REQ-017 | Proposer l'unicast multi-destination | Plusieurs destinations reçoivent un profil ; erreur sur une destination isolée et visible. |
| REQ-018 | Proposer le multicast LAN | Groupe/interface explicitement configurés ; plusieurs récepteurs observés sans émission unicast additionnelle par récepteur. |
| REQ-019 | Distinguer client, abonnement et destination | Table avec identité disponible, transport, source, profil, état et débit ; un destinataire UDP sans handshake reste une destination non confirmée. |
| REQ-020 | Définir le protocole natif versionné | Séquence, époque, format, fréquence d'échantillonnage, référence temporelle et révision de configuration ont une sémantique documentée et des vecteurs de test. |
| REQ-021 | Gérer la taille des datagrammes | Budget de taille adapté au réseau cible ; traitement des limites, pertes, réordonnancement et paquets invalides vérifié ; aucune garantie UDP de livraison annoncée. |
| REQ-022 | Permettre la découverte facultative | Un client natif découvre le service quand le réseau le permet et peut toujours utiliser l'adresse manuelle. |
| REQ-023 | Encadrer l'accès LAN/VPN | Interfaces et ports visibles/configurables ; pas d'ouverture publique automatique ni modification silencieuse du pare-feu ; politique d'accès à arbitrer. |

Le débit émis n'est pas une preuve du débit reçu. Le serveur ne peut pas déduire le nombre réel d'auditeurs multicast ni les pertes à réception sans télémétrie correspondante. Ces informations doivent être distinguées dans l'interface.

### 7.4 Interface et exploitation

| ID | Exigence | Critère observable |
|---|---|---|
| REQ-024 | Fournir une GUI normale | Écrans Device, Spectrum, RF Profiles, Streams & Clients, Network, Recorder et Diagnostics ; unités et état RX cohérents. |
| REQ-025 | Fournir le Compact Monitor | Fréquence, mini-spectre et état visibles ; option premier plan, taille/position mémorisées, retour au mode normal sans interruption du flux. |
| REQ-026 | Garder une interface réactive | Acquisition/DSP indépendants du rafraîchissement GUI ; un ralentissement d'affichage ne bloque pas les données ; test de redimensionnement en charge. |
| REQ-027 | Afficher l'état effectif | Reconnexion, saturation, absence de source et erreur de configuration visibles dans les deux modes ; un spectre figé n'est pas présenté comme vivant. |
| REQ-028 | Sauvegarder des presets complets | Matériel, RF, profils et destinations restaurables ; équipement absent ou capacité incompatible signalés ; paramètres sensibles non exportés en clair. |
| REQ-029 | Démarrer automatiquement sur option | Auto-connexion et auto-start indépendants ; équipement manquant provoque un état explicite, sans substitution silencieuse par un autre SDR. |
| REQ-030 | Fonctionner en headless | Même validation de configuration et même distribution ; démarrage/arrêt et journaux utilisables sans GUI. |
| REQ-031 | Enregistrer et rejouer l'IQ | Données et métadonnées cohérentes, trous identifiés, disque plein géré sans bloquer les clients ; vitesse/fin de replay définies. |
| REQ-032 | Réagir aux pannes | Déconnexion, absence de données et échec de reconnexion testables ; tentatives bornées ; reprise crée une époque distincte si nécessaire. |
| REQ-033 | Fournir diagnostics et simulation | Source synthétique déterministe et défauts injectables ; compteurs et logs permettent de localiser la couche concernée. |
| REQ-034 | Borner les ressources | Files et buffers bornés, limites configurables et raison de refus visible ; arrêt propre sans croissance mémoire persistante sur un essai de durée défini. |

## 8. Matrice de compatibilité

L'ordre de priorité est acquis ; chaque mode d'intégration et sa validation restent spécifiques. Référence historique : [guide clients V0.2](https://github.com/f5jwf/SDR_Bridge/blob/7efd536e059e60130884e6aef3a23e1e5aea79dc/docs/CLIENT_SETUP.md).

| Client | Cible | Preuve nécessaire | Statut du futur produit |
|---|---|---|---|
| ANTRACK | Préserver l'intégration locale ; débits prioritaires 192/96 kS/s | Version client identifiée, qualité spectrale, durée et comportement lors d'un retune | À qualifier |
| HDSDR | Préserver l'ExtIO locale et ses contraintes d'architecture | Chargement DLL, réception, fréquence affichée, refus/gestion du contrôle distant | À qualifier |
| SDR++ | Profil ou adaptateur réseau selon le module/version réellement utilisé | Format exact, configuration du récepteur et flux reçu vérifiés | Mode exact ouvert |
| QMAP/Linrad | Connecteur TIMF2 envisagé | Spécification du framing, horodatage et essai réel avec version ciblée | À spécifier et qualifier |
| Python | Petit consommateur de référence du protocole natif | Décodage, séquences, formats, trous et changement de configuration | À développer |
| WSJT-X | Chaîne audio externe via un logiciel de réception approprié | Parcours distinct vérifié ; aucune promesse d'ingestion IQ directe | Extension de validation |
| Code300-32, Centurion, autres | Étude individuelle | Interface d'entrée et licence/environnement disponibles | Hors compatibilité garantie initiale |

L'ExtIO existante est une cible de non-régression, pas la preuve d'une ExtIO réseau future. Les ponts réseau supplémentaires doivent faire l'objet d'un périmètre explicite.

## 9. Architecture conceptuelle proposée

| Concept | Responsabilité et relation |
|---|---|
| BridgeController | Cycle de vie, validation et autorité opérateur ; utilisé par GUI et headless. |
| DeviceManager / DeviceCapabilities | Inventaire, identité et capacités matérielles. |
| DeviceSession | Une ouverture de SDR, son état et ses réglages ; plusieurs possibles ultérieurement. |
| IQSource / SourceStream | Interface commune matériel, simulation et replay ; flux identifié, configuration et temporalité. |
| RFProfileManager | Règles RF appliquées par l'autorité centrale. |
| StreamProfile | Description réutilisable des paramètres de sortie ; son édition doit avoir une sémantique explicite. |
| ProcessingPipeline | Traitement rattaché à une source ; partagé uniquement entre demandes équivalentes. |
| StreamSession | Instance de distribution d'une sortie, indépendante de l'identité d'un logiciel client. |
| ClientSession / Subscription | Identité et état connus du client ; abonnement reliant client, source, profil et transport. |

La granularité des objets sera confirmée par l'audit. Un appareil multi-canaux peut produire plusieurs flux : le nombre de canaux pris en charge en V1 reste ouvert. Une extension multi-SDR ne doit pas exiger de supprimer les identités introduites ici.

Contrats à détailler avant leurs lots :

- Blocs IQ : type, disposition mémoire, unités, nombre d'échantillons complexes, source, époque, séquence, temps, validité, discontinuités et révision de configuration.
- Mémoire partagée : version ABI, taille/alignement, durée de vie, compteurs, rattrapage d'un lecteur et compatibilité Python/C++.
- Contrôle : enregistrement, abonnement, heartbeat, erreurs, droits, versions compatibles et changements de configuration.
- UDP natif et profils tiers : en-têtes, endianness, tailles, unités, politique des pertes et vecteurs binaires.
- Profils RF/presets : version du schéma, validation, priorité des règles, import/export et comportement en cas d'échec partiel.
- DSP : gabarit du filtre, retard, gestion des bords, conversion numérique, correspondance des compteurs avant/après resampling.

Ces contrats servent à fermer les décisions nécessaires au lot actif ; leur présence dans cette liste n'impose pas de rédiger six grands documents avant tout progrès.

## 10. Qualité, performance et environnement

Windows est la cible initiale proposée compte tenu des intégrations existantes ; versions, architectures et éventuel support Linux restent à confirmer (O-02). Les pilotes, bibliothèques natives et conditions de redistribution doivent être vérifiés avant packaging.

Exemple de dimensionnement, sans garantie de performance : 2 MS/s en CS16 correspondent à 8 MB/s de données IQ, soit 64 Mbit/s avant en-têtes. Chaque destination unicast supplémentaire consomme ce débit ; le multicast mutualise l'émission sur le lien concerné. Les lecteurs partagés consomment aussi de la bande passante mémoire lorsqu'ils lisent.

| Paramètre | État | Condition pour le fixer |
|---|---|---|
| Modèles SDR et versions de pilotes | Ouvert | Inventaire du matériel réellement disponible |
| Taux source et formats garantis | Ouvert | Capacités matérielles et besoin des clients prioritaires |
| Nombre et mélange de lecteurs/sorties garantis | Ouvert | Machine de référence, réseau et profils DSP définis |
| Latence bout en bout | Ouvert | Points de mesure, horloges et percentile explicités |
| Pertes tolérées | Ouvert | Couche mesurée, charge et durée d'essai définies |
| CPU, RAM et durée d'endurance | Ouvert | Seuils définis avant acceptation du lot de qualification |
| Réjection d'alias et ondulation passante | Ouvert | Besoin RF et facteurs de conversion validés |
| Débit d'enregistrement et espace disque | Ouvert | Flux choisi, support disque et politique de rotation |

Un profil de référence pourra démarrer à 2 MS/s CS16 avec sorties ANTRACK 192/96 kS/s, mais cette proposition ne devient pas une garantie sans mesure. Les budgets et preuves seront enregistrés par configuration testée.

## 11. Stratégie d'acceptation

| Famille de preuve | Exigences principales | Preuve attendue |
|---|---|---|
| Tests source et contrats | REQ-004 à REQ-007, REQ-010 à REQ-015, REQ-020 à REQ-021 | Vecteurs déterministes, bornes, erreurs et invariants |
| Intégration simulée | REQ-003, REQ-008 à REQ-010, REQ-016 à REQ-023, REQ-028 à REQ-034 | Plusieurs consommateurs, ralentissements, pertes et arrêt/reprise |
| GUI native | REQ-024 à REQ-029 | Interactions Qt, inspection visuelle, mise à l'échelle écran et acquisition continue |
| Matériel réel | REQ-001 à REQ-007, REQ-011 à REQ-014, REQ-032 | Modèle/pilote/version documentés et traces de réception |
| Logiciels tiers | Matrice du §8 | Version, configuration, résultat mesuré et limites de chaque client |
| Charge et endurance | REQ-008 à REQ-014, REQ-017 à REQ-018, REQ-026, REQ-031 à REQ-034 | Machine, réseau, durée, profils et seuils convenus |

Playwright n'est pas retenu comme preuve directe des widgets PyQt5. La validation SR devra être adaptée à l'application native, sans désactiver l'exigence d'inspection visuelle. L'outil Qt précis sera choisi après inspection des tests existants.

Une preuve simulée ne remplace pas une preuve matérielle requise. Un lot avec travail technique restant ne sera pas envoyé en simple « test utilisateur ». Les preuves indisponibles sont consignées avec leur raison et la prochaine action.

## 12. Intégration de SR Method 4.1.0

Référence : [pack SR v4.1.0](https://github.com/syl2042/Aurora_SR_method_codex_pack/tree/v4.1.0), commit `596a681742e664dc9fdbbdc26783d62bba3f77f0`. Une évolution ultérieure de `main` ne change pas implicitement cette référence.

L'installation effective sera faite dans le dépôt applicatif choisi, après inventaire de son état. Un dépôt avec marqueurs SR existants doit suivre le parcours de mise à niveau prévu par le pack ; l'absence de marqueurs appelle une installation initiale. Examiner la prévisualisation et le contrôle post-installation, sans déduire le succès d'un simple code de sortie.

Le fonctionnement cible repose sur trois questions pour chaque lot : quel périmètre est autorisé, quelle preuve couvre le résultat et quelle activation éventuelle est incluse ? La compilation nécessaire à une vérification et l'activation d'un environnement partagé doivent être explicitement distinguées. Les procédures sont chargées selon le besoin ; une tâche locale ne déclenche pas la lecture de tout le dossier produit.

Les quatre skills principales sont `aurora-diagnose`, `aurora-ui-visual-qa`, `aurora-architecture-check` et `aurora-lot-runner`. Prévoir également les deux optionnelles `aurora-to-prd` et `aurora-domain-skill-factory` pour les phases concernées. Ne pas restaurer les cinq anciennes skills supprimées ; ne pas charger tout le catalogue à chaque tâche. Référence : [profil SR](https://github.com/syl2042/Aurora_SR_method_codex_pack/blob/v4.1.0/core/PROJECT_PROFILE.template.yaml).

Les connaissances métier locales à formaliser en priorité portent sur Soapy/RF, IQ/mémoire partagée, DSP, réseau/compatibilité et Qt temps réel. Leur découpage en skills dépendra du code et des besoins réels ; il n'est pas nécessaire de créer un catalogue volumineux dès maintenant.

Pour la continuité, utiliser un état de tâche compact quand il est utile. Les REQ du présent PRD pourront être reliées aux lots et aux preuves. Conserver les historiques existants sans conversion globale. Une réparation reprend l'exigence concernée plutôt que de la faire disparaître sous un nouveau lot. Référence : [définition des lots SR 4.1](https://github.com/syl2042/Aurora_SR_method_codex_pack/blob/v4.1.0/prompts/09_define_sr_lots_from_scope.md).

L'intégration Nexus est décrite dans [l'évaluation MCP](../tooling/NEXUS_MCP_EVALUATION.md). L'état initial proposé est `core`. Le passage à `nexus_kg` attend une connexion vérifiée et une politique explicitant les capacités réelles. Cette prescription décrit le futur environnement ; aucun fichier de configuration SR n'est installé ici.

## 13. Premières passes proposées

Ce découpage sert à préparer le travail. Il ne constitue pas un registre de lots validés ni un ordre de coder immédiatement. Les critères détaillés du §7 sont hérités par chaque lot.

| Lot proposé | Périmètre / exclusions | Dépendances | Vérification de sortie | Activation |
|---|---|---|---|---|
| SDB-FOUNDATION-001 | Choix du dépôt, bootstrap SR 4.1, audit ciblé et rapprochement PRD/code ; pas de modification applicative | O-07 | Révision de base, état des tests, état SR et écarts documentés | Environnement de développement seulement |
| SDB-CORE-001 | Cycle de vie, identités et contrats de flux, simulation ; pas de multi-SDR simultané | FOUNDATION | REQ-003, REQ-013 à REQ-015, REQ-033 ; consommateurs identifiés | Tests locaux |
| SDB-RF-001 | Soapy générique, contrôles, profils RF ; pas de TX ni de bail client | CORE, O-02, O-03, O-08 | REQ-001 à REQ-007 ; simulation puis SDR de référence | Essai matériel planifié |
| SDB-STREAM-001 | Distribution locale et DSP mutualisé ; préserver les clients locaux | CORE, O-04 | REQ-008 à REQ-014, REQ-034 ; filtres et clients prioritaires | Essais ANTRACK/HDSDR |
| SDB-NET-001 | Contrôle natif, UDP uni/multicast, télémétrie et découverte ; pas d'exposition publique | CORE, STREAM, O-05, O-06 | REQ-016 à REQ-023 et REQ-034 ; profils tiers qualifiés séparément | Réseau LAN/VPN d'essai |
| SDB-UI-001 | GUI normale, compact, presets et démarrage ; pas de GUI distante | CORE, RF, STREAM ; NET pour ses écrans | REQ-024 à REQ-030 ; contrôle Qt et réception continue | Application locale |
| SDB-OPS-001 | Record/replay, watchdog, reprise et diagnostics consolidés | CORE, STREAM, O-09 | REQ-028 à REQ-034 ; fautes injectées et fichiers relus | Essais locaux/matériels |
| SDB-QUAL-001 | Qualification des clients, charge, installation et documentation utilisateur | Lots requis ci-dessus, O-02 à O-06, O-09 | Matrice d'acceptation complète et limites publiées | Installation test ; publication distincte |

Passes envisagées : préparation ; cœur/acquisition/distribution ; réseau/interface/exploitation ; qualification. L'ordre précis peut être ajusté à l'audit sans déplacer silencieusement les exigences hors V1. Les essais matériels indisponibles ne bloquent pas les travaux simulés indépendants, mais restent nécessaires à l'acceptation correspondante.

L'évaluation Nexus constitue une piste d'outillage parallèle, sans dépendance obligatoire dans cette chaîne.

## 14. Décisions ouvertes et moment de décision

| ID | Élément à trancher | Base de travail proposée | À fermer avant |
|---|---|---|---|
| O-01 | Multi-SDR simultané dès la première version utilisable ? | Garder DEC-003 ; prévoir une passe dédiée ultérieure | Validation du périmètre de livraison |
| O-02 | OS, architecture, SDR, canaux et pilotes de référence | Windows initial ; un flux RX actif ; modèles à fournir | RF et qualification |
| O-03 | Priorités des profils RF, bornes et dérogation manuelle | Règles déterministes et aucun changement caché | RF |
| O-04 | Gabarits DSP et budgets de performance | Mesurer d'abord un profil 2 MS/s vers 192/96 kS/s | STREAM et qualification |
| O-05 | Versions ANTRACK/HDSDR/SDR++/QMAP et protocoles cibles | Priorité historique conservée, preuve par client | Adaptateur correspondant |
| O-06 | Authentification locale/LAN, admission, interfaces et VPN | LAN/VPN seulement ; droits de lecture ; paramètres explicites | NET |
| O-07 | Dépôt/branche de développement et politique de compatibilité avec l'amont | Réutiliser la base de Philippe après audit | FOUNDATION et toute modification applicative |
| O-08 | Place du backend SDRplay natif existant | Préserver tant que sa substitution n'est pas prouvée | RF |
| O-09 | Enregistrement : source/profil, rotation, disque plein ; replay : cadence et fin | SigMF principal ; arrêt d'enregistrement isolé ; replay via IQSource | OPS |
| O-10 | Routage manuel, édition de profils actifs et récupération partielle des presets | Associations explicites, aperçu des impacts | NET/UI |
| O-11 | Endpoint MCP, authentification et capacités Nexus | Évaluation de lecture avec repli Core | Essai Nexus ; sans bloquer le PRD |

Les décisions ouvertes ne justifient pas de suspendre toute la préparation. Seuls les travaux dépendant de leur réponse doivent attendre. La priorité immédiate est de relire le périmètre, choisir le dépôt de développement et inventorier le matériel/client de référence.

## 15. Risques suivis

| Risque | Réponse prévue |
|---|---|
| Régression des clients existants lors d'un changement d'ABI | Tests de contrat et versions explicites ; migration/adaptateur étudiés avant rupture |
| Alias ou amplitude erronée après resampling | Gabarit mesurable, vecteurs synthétiques et essais de réception |
| Confusion entre temps matériel et heure du PC | Origine/validité du temps dans les contrats et dans les diagnostics |
| Blocage acquisition par GUI, disque ou client lent | Files bornées, indépendance des consommateurs et injection de retards |
| Compatibilité commerciale annoncée sans essai | Matrice versionnée ; statut non qualifié conservé jusqu'à la preuve |
| Multi-SDR ajouté tardivement à une source implicite globale | Identités de source et ownership dans les contrats initiaux |
| Divergence PRD / code / graphe Nexus | Distinguer cible et état réel ; révision d'index et lecture du code |
| Surcharge de processus SR sur une petite modification | Chargement conditionnel, mémoire compacte et preuve proportionnée |

## 16. Livrables suivants

La v0.1 comprend ce PRD et l'évaluation Nexus. Le Project Pack exécutable sera complété au fil des décisions par les contrats nécessaires, la configuration SR adaptée, la matrice de tests et les lots validés. Il n'est pas encore présenté comme installé ou prêt à lancer automatiquement le développement.
