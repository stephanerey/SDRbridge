# SDRbridge — PRD v0.3

Date : 13 octobre 2026. Responsable produit : Stéphane. Méthode installée : SR4.1.0. Statut : pack de réalisation préparé, nouvelles fonctionnalités non engagées. [S6](../specs/06_IMPLEMENTATION_BASELINE.md) fixe les choix d'exécution et complète obligatoirement ce PRD ; [DESIGN](DESIGN.md) fixe les parcours Qt.

Cette version remplace la v0.1 comme point d'entrée. Les détails d'exécution sont externalisés en spécifications courtes par domaine, afin de donner à Codex les seuls éléments nécessaires à chaque lot. L'historique reste disponible dans [l'archive v0.1](../archive/PRD_v0.1.md).

## 1. Produit et résultat attendu

SDRbridge centralise l'acquisition RX et les réglages d'un SDR, puis distribue le signal IQ à plusieurs logiciels. Il permet de régler la station, de choisir les profils de sortie, de suivre l'état des clients et de garder un moniteur compact pendant l'utilisation d'ANTRACK, HDSDR ou d'autres récepteurs compatibles.

Le produit doit être utilisable sans Nexus et sans service cloud. Le logiciel existant de Philippe est importé au commit épinglé, audité de façon ciblée et testé ; il reste une base à préserver autant que pertinent, pas la réalisation du présent PRD.

## 2. Périmètre acquis

- RX uniquement ; un SDR actif en V1, plusieurs détectables ; identités et contrats extensibles au multi-SDR.
- SoapySDR comme interface matérielle principale ; adaptateurs spécifiques lorsque justifiés ; rôle du backend SDRplay natif à confirmer après audit.
- Autorité matérielle unique dans le cœur, commandée par l'opérateur via GUI ou configuration headless. Les clients IQ ne changent pas la radio.
- PyQt5/PyQtGraph, interface normale et Compact Monitor ; même cœur headless.
- Mémoire partagée locale, contrôle et données réseau séparés, UDP unicast/multicast ; pas de plafond fixe à quatre clients.
- Resampling filtré et conversions mutualisés par source et paramètres effectifs.
- Profils RF, presets complets, reconnexion/watchdog, simulation, diagnostics, enregistrement/replay cible SigMF.
- Accès distant via VPN ; découverte mDNS facultative ; configuration manuelle toujours possible.
- Qualification : ANTRACK, HDSDR, SDR++ et client Python de référence. QMAP reste une extension différée faute de version/interface identifiées ; aucune compatibilité QMAP annoncée en V1.

Hors V1 : TX, bail de contrôle client, DDC par client, cohérence de phase entre SDR, exposition publique Internet et contrôle graphique distant. Le multi-SDR simultané ne sera avancé en V1 que par décision explicite.

## 3. Niveaux de livraison

**Tranche A — première chaîne utile :** une source, flux local fiable, ANTRACK/HDSDR, diagnostics essentiels et contrôle matériel. **Tranche B :** réseau, nouvelle GUI et presets. **Tranche C :** record/replay, endurance et qualification complète. Ce découpage est une proposition d'ordre ; il ne retire aucune exigence à la cible V1 complète.

Un livrable limité à la tranche A doit porter son périmètre réel, sans être annoncé comme V1 complète. La qualification d'un client vaut pour une version et une configuration identifiées.

## 4. Exigences et routage vers les spécifications

Identifiants conservés depuis la v0.1. L'audit initial identifie les écarts dans PREPARATION_REPORT ; aucune exigence complète n'est certifiée par les quatre tests amont. Les preuves ci-dessous sont des cas à exécuter, pas des résultats obtenus.

| ID | Exigence | Spécification | Preuve |
|---|---|---|---|
| REQ-001 | Détecter et identifier chaque appareil | S1 §2, S2 §2 | AC-01 |
| REQ-002 | Exposer ses capacités réelles | S1 §2 | AC-01 |
| REQ-003 | Ouvrir, démarrer, arrêter, fermer proprement RX | S1 §1 | AC-02 |
| REQ-004 | Valider et afficher les paramètres appliqués | S1 §2 | AC-03 |
| REQ-005 | Préserver l'autorité matérielle centrale | S1 §2, S4 §2 | AC-03, AC-09 |
| REQ-006 | Appliquer les règles RF déterministes | S1 §3 | AC-04 |
| REQ-007 | Signaler reconfiguration et discontinuités | S1 §1, S2 §3 | AC-03, AC-05 |
| REQ-008 | Supprimer le plafond fixe de quatre lecteurs | S2 §4 | AC-06 |
| REQ-009 | Isoler les lecteurs lents | S2 §4 | AC-06 |
| REQ-010 | Mutualiser les traitements identiques | S2 §5 | AC-07 |
| REQ-011 | Resampler avec filtre anti-alias mesuré | S3 §2 | AC-08 |
| REQ-012 | Convertir correctement les formats IQ | S3 §1 | AC-08 |
| REQ-013 | Conserver des compteurs et temps explicites | S2 §3, S3 §3 | AC-05, AC-08 |
| REQ-014 | Distinguer les pertes par couche | S2 §6 | AC-05, AC-10 |
| REQ-015 | Préparer plusieurs sources sans mélange | S2 §2, §5 | AC-07 |
| REQ-016 | Séparer contrôle et IQ | S4 §2 | AC-09 |
| REQ-017 | Distribuer en unicast multi-destination | S4 §3 | AC-10 |
| REQ-018 | Distribuer en multicast LAN | S4 §3 | AC-10 |
| REQ-019 | Distinguer clients, abonnements, destinations | S1 §4, S2 §2 | AC-09, AC-11 |
| REQ-020 | Versionner le protocole natif | S4 §4 | AC-10 |
| REQ-021 | Borner et valider les datagrammes | S4 §3–4 | AC-10 |
| REQ-022 | Découvrir le service sans dépendre de mDNS | S4 §5 | AC-09 |
| REQ-023 | Limiter l'accès aux interfaces autorisées | S4 §2–3 | AC-09 |
| REQ-024 | Fournir les écrans normaux | S1 §4 | AC-11 |
| REQ-025 | Fournir le Compact Monitor | S1 §5 | AC-11 |
| REQ-026 | Découpler GUI et acquisition | S1 §5, S2 §4 | AC-11, AC-14 |
| REQ-027 | Afficher l'état effectif et les erreurs | S1 §4–5 | AC-11, AC-13 |
| REQ-028 | Sauvegarder/restaurer les presets complets | S5 §1 | AC-12 |
| REQ-029 | Démarrer automatiquement sur option | S5 §1–2 | AC-12 |
| REQ-030 | Fonctionner en headless | S5 §2 | AC-12 |
| REQ-031 | Enregistrer et rejouer | S5 §4 | AC-15 |
| REQ-032 | Watchdog et reconnexion contrôlés | S5 §3 | AC-13 |
| REQ-033 | Diagnostics et source simulée reproductibles | S2 §6, S5 §5 | AC-05, AC-13 |
| REQ-034 | Borner mémoire et charge | S2 §4, S5 §3–4 | AC-06, AC-14 |

S1 : [Comportements et écrans](../specs/01_BEHAVIOR_UI.md). S2 : [Contrats du cœur](../specs/02_CORE_CONTRACTS.md). S3 : [DSP](../specs/03_DSP.md). S4 : [Réseau](../specs/04_NETWORK.md). S5 : [Exploitation](../specs/05_OPERATIONS.md). AC : [acceptation](../verification/ACCEPTANCE.md).

## 5. Compatibilité et performance

Préserver les chemins locaux existants ANTRACK et HDSDR avant de prétendre à une compatibilité réseau de ces logiciels. SDR++ et QMAP nécessitent des protocoles et versions identifiés ; le protocole natif ne les rend pas automatiquement compatibles. WSJT-X relève d'un parcours audio externe, pas d'une promesse d'entrée IQ native.

Un profil de test simulé est proposé : source 2 MS/s CS16, sorties 192 et 96 kS/s, cinq lecteurs locaux, deux destinations natives unicast. Il démontre des invariants ; il n'établit pas la capacité de la machine réelle.

Cible confirmée par Stéphane : **SDRplay RSPdx, Windows 11 Pro, HDSDR 2.81a, SDR++ 1.2.1**. ANTRACK sera qualifié sur le dernier état du dépôt identifié dans [ANTRACK_BASELINE](../reference/ANTRACK_BASELINE.md), version déclarée 2.1.0. Les pilotes réellement installés, seuils CPU/mémoire, latence et détails de connexion des clients restent à mesurer ou préciser.

## 6. Exécution et décisions restantes

La méthode est détaillée dans [SR41_INTEGRATION](../tooling/SR41_INTEGRATION.md). Les [lots](../work/BACKLOG.md) donnent les actions et les preuves à produire. Le [registre de décisions](DECISIONS.md) donne les paramètres techniques proposés et les vrais blocages.

Le pack v0.3 fournit les contrats, defaults, preuves attendues et passes de réalisation. L'import et les tests amont sont effectués. Le [prompt de lancement](../handoff/START_IMPLEMENTATION.md) autorisera l'implémentation avec S6 ; les essais matériels, déploiements et publication restent séparés. Une incompatibilité observée appelle une correction documentée, pas une invention de capacités.
