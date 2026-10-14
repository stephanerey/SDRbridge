# Lots de réalisation — v0.3

BASE est effectué ; les autres lots restent proposés jusqu'au prompt de lancement. Statuts officiels : `docs/codex/SR_LOTS.yaml`. [S6](../specs/06_IMPLEMENTATION_BASELINE.md) tranche les anciennes mentions « à définir/valider » : ring v2 versionné, FIR, versions, SDK, protocoles tiers, SigMF, budgets et schémas. Les actions historiques ci-dessous sont à lire avec ces décisions, sans refaire la préparation.

## SDB-BASE-001 — Référence applicative et méthode

**Dépendance :** autorisation d'initialiser Git/importer la base, O-07. **Entrées :** état réel, référence amont, intégration SR41 et inventaire de recette. **Périmètre :** préparation du dépôt ; aucune refonte de l'application.

Actions :

1. Vérifier le contenu et les changements locaux ; garder tous les documents de cette préparation.
2. Relever le dépôt distant et la branche de travail souhaitée ; ne pas inventer une branche ou un push dans l'autorisation documentaire actuelle.
3. Importer la base amont autorisée en conservant sa provenance et les fichiers de licence présents. Ne pas écraser un fichier de travail homonyme sans rapprochement.
4. Lire les modules de démarrage, acquisition, clients et les tests existants. Relever les interfaces natives réellement utilisées.
5. Établir un environnement de test isolé du Python d'ANTRACK ; ne pas installer de pilote système comme effet secondaire.
6. Exécuter les tests amont non matériels, conserver résultat initial et erreurs préexistantes.
7. Préparer l'installation SR depuis la révision figée, inspecter la prévisualisation, intégrer les règles locales, effectuer le contrôle post-installation après autorisation correspondante.

**Livrables :** code de référence identifié, résultat de tests initial, état SR réel, carte courte des modules et écarts REQ ↔ code. **Preuve :** provenance et tests reproductibles. **Exclus :** changement DSP, ABI, GUI, pilotes, Nexus write, publication. **Arrêt :** conflits locaux, source inaccessible ou action d'installation non autorisée. **Activation :** environnement de développement uniquement.

## SDB-CORE-001 — Sessions et flux explicites

**Dépendance :** BASE. **Lire :** S1 §1, S2 §1–3/6. **Couvre :** REQ-003, REQ-007, REQ-013 à REQ-015, REQ-033. **Cibles initiales :** `model.py`, `bridge.py`, `source.py` et leurs consommateurs confirmés à l'audit.

Actions : ajouter identités/époques et temps explicitement typés au contrat interne ; sérialiser le cycle de vie ; garder une seule source active ; adapter la simulation déterministe ; exposer les états sans changer l'ABI partagée. Ajouter les tests de transitions et de discontinuité dans la suite existante. Refuser double start et activation TX.

**Preuves :** AC-02, AC-05 ; vérification des consommateurs et tests historiques. **Livrable :** contrats internes et source simulée fiables. **Exclus :** multi-SDR réel, réseau v2, GUI nouvelle, retrait du backend natif. **Activation :** simulation locale. **Arrêt :** contrat natif incompatible non résolu.

## SDB-RING-001 — Distribution locale sûre

**Dépendance :** CORE. **Lire :** S2 §4, référence amont. **Couvre :** REQ-008, REQ-009, REQ-034. **Cibles :** `ring.py`, enregistrement des clients, lecteurs Python et ExtIO.

Actions : identifier tous les plafonds clients ; remplacer le plafond arbitraire par une politique configurable ; analyser les accès interprocessus Python/C++ ; définir la publication/lecture cohérente et la durée de vie des vues ; préserver le wire v1 ou faire valider une migration versionnée ; garantir la libération des lecteurs sans destruction prématurée du segment.

**Preuves :** AC-06, tests amont, lecture concurrente pendant wrap avec motifs de payload identifiant leur séquence. **Livrable :** aucun bloc déchiré accepté et lecteur lent isolé. **Exclus :** promesse de zéro-copie total, modifications de protocole réseau. **Activation :** processus locaux simulés, puis clients historiques quand disponibles.

## SDB-DSP-001 — Profils et resampling partagé

**Dépendance :** CORE/RING ; P-09/P-10 validés ou remplacés. **Lire :** S2 §5, S3, interface ANTRACK identifiée. **Couvre :** REQ-010 à REQ-014.

Actions : normaliser les profils ; implémenter la clé de mutualisation et son comptage de références ; sélectionner un FIR/polyphase après mesure du gabarit et des dépendances ; conserver l'état entre blocs ; documenter retard et index ; remplacer le chemin ANTRACK seulement après vecteurs de non-régression ; livrer un chemin bypass sans DSP inutile.

**Preuves :** AC-07/08 et sortie mesurée aux deux taux prioritaires. **Livrable :** traitement mutualisé et gabarit démontré. **Exclus :** DDC, upsampling, normalisation automatique de puissance. **Arrêt :** ajout de dépendance non autorisé ou gabarit impossible au budget constaté. **Activation :** simulation, puis essai ANTRACK séparé.

## SDB-RF-001 — RSPdx, Soapy et règles RF

**Dépendance :** CORE, inventaire pilotes, P-03/P-04. **Lire :** S1 §1–3, S2 §2–3 et état amont. **Couvre :** REQ-001 à REQ-007, REQ-032 pour les erreurs de backend.

Actions : découvrir capacités sans ouvrir TX ; distinguer demandé/effectif ; exposer gains nommés et antennes ; implémenter application sérialisée et readback ; appliquer les règles RF ; identifier les contraintes SDRplay réelles ; préserver le backend natif existant tant que le remplacement n'est pas qualifié.

**Preuves :** AC-01/03/04 en simulation puis RSPdx réel, avec pilote et réglages enregistrés. **Livrable :** fiche des capacités RSPdx observées et comportements d'erreur. **Exclus :** supposer la compatibilité de tous les drivers Soapy, changer les pilotes du PC silencieusement. **Activation :** ouverture du SDR uniquement pendant un essai matériel annoncé et autorisé.

## SDB-NET-001 — Protocole natif et distribution

**Dépendance :** CORE/DSP, validation de S4 et politique O-06. **Lire :** S4, S2 §2/6. **Couvre :** REQ-016 à REQ-023.

Actions : isoler contrôle historique et natif ; implémenter enveloppes/erreurs/baux ; valider identités et destinations ; coder encodeur/parseur v2 avec vecteurs indépendants ; distribuer unicast/multicast depuis le DSP partagé ; fournir un petit récepteur natif de référence ; limiter files et requêtes ; ajouter mDNS facultatif après connexion manuelle fonctionnelle.

**Preuves :** AC-09/10 en loopback puis LAN autorisé. **Livrable :** contrat réseau et mesures émission/réception distinguées. **Exclus :** déclarer SDR++/QMAP compatibles, administration RF distante, ouverture Internet. **Activation :** réseau désactivé par défaut ; activation LAN séparée de la compilation.

## SDB-UI-001 — Interface normale et compacte

**Dépendance :** CORE/RF/DSP ; NET pour actions réseau réelles. **Lire :** S1 §4–5, S5 §1. **Couvre :** REQ-019, REQ-024 à REQ-029.

Actions : réutiliser le contrôleur sans dupliquer la logique RF ; construire les écrans et états vides/erreurs ; distinguer brouillon/appliqué ; créer le service de spectre partagé ; implémenter compact et géométrie récupérable ; brancher profils et destinations seulement sur des fonctions existantes ; désactiver une fonction non livrée avec explication, sans simulacre de succès.

**Preuves :** AC-11/12 pertinents ; instrumentation de continuité ; inspection Qt native. **Livrable :** parcours opérateur complets sur la tranche disponible. **Exclus :** réécriture du DSP dans les widgets, GUI distante. **Activation :** application locale.

## SDB-OPS-001 — Exploitation et capture

**Dépendance :** CORE/DSP/RF, UI pour les contrôles graphiques ; standard SigMF à figer. **Lire :** S5. **Couvre :** REQ-028 à REQ-034.

Actions : versionner persistance et presets ; arrêt atomique des fichiers ; headless et arrêt propre ; watchdog/reprises bornées ; recorder consommateur indépendant ; validation de captures SigMF ; replay comme source ; export diagnostic non sensible.

**Preuves :** AC-12/13/15, erreurs de disque et fichiers invalides. **Livrable :** exploitation sans GUI et capture/replay reproductibles. **Exclus :** service Windows administré, suppression automatique de captures, restauration de contrôle client. **Activation :** application locale ; aucun changement système automatique.

## SDB-QUAL-001 — Compatibilité et qualification de livraison

**Dépendance :** lots de la tranche livrée, seuils approuvés. **Lire :** plan ACCEPTANCE, références clients et état courant. **Couvre :** toute exigence de la tranche avec preuves restantes.

Actions : rapprocher REQ et preuves ; qualifier RSPdx + ANTRACK au commit retenu + HDSDR 2.81a ; identifier le module SDR++ 1.2.1 et construire/qualifier son profil dans un sous-périmètre approuvé ; faire de même pour QMAP si version et documentation disponibles ; mesurer endurance ; tester installation isolée ; documenter limitations et procédure de retour à la version précédente.

**Preuves :** AC-14/16/17 et cas non encore couverts. **Livrable :** matrice de compatibilité versionnée et rapport de qualification. **Exclus :** annoncer « tous les clients compatibles », masquer les preuves manquantes ou publier automatiquement. **Activation :** installation de test ; release publique sur instruction distincte.

## Passes proposées

1. BASE, seul, pour obtenir la référence et la méthode.
2. CORE puis RING ; DSP et RF selon leurs dépendances.
3. NET, UI et OPS, en respectant les fonctions réellement disponibles.
4. QUAL, avec limites explicites de la tranche.

Ne pas lancer une passe suivante par simple fin de la précédente sans autorisation. Le prompt de lancement autorise explicitement les passes002 à004, avec préconditions et preuves, mais aucune passe supplémentaire. La piste Nexus reste indépendante. Une recette réelle non exécutée reste user_testing ; écrire tous les fichiers ne suffit pas à clore un lot.
