# S5 — Configuration, headless, reprise et enregistrement

Statut : comportements proposés v0.2. Couverture : REQ-028 à REQ-034. Paramètres P-06/P-13/P-14 : [DECISIONS](../product/DECISIONS.md).

## 1. Configuration et presets

Séparer la configuration du programme, les presets de station et la géométrie GUI. Chaque fichier porte une version de schéma. Écriture atomique par fichier temporaire dans le même dossier puis remplacement ; conserver la dernière configuration valide. Un fichier invalide ne doit pas être réécrit silencieusement avec des valeurs par défaut.

Configuration de programme : backend/source choisie, identité matérielle, réglages RX, profils, destinations, tailles de buffers, délais, logging et options auto-connect/auto-start. Les références de secrets sont des noms, pas leurs valeurs. Le chemin de stockage Windows est à fixer au packaging selon les conventions du projet importé ; aucune configuration utilisateur dans le code source.

Preset : nom, version, sélecteur de matériel, fréquence, taux, bande passante, antenne, gains/AGC, profil RF et sa suspension, profils de sortie et destinations opérateur. Un preset ne contient ni client_id transitoire, ni epoch, ni token. Le bouton « Sauvegarder l'état courant » sauvegarde les valeurs effectives, avec indication des paramètres non relus.

Chargement : analyser sans agir, comparer aux capacités et à l'état actuel, montrer les changements et les incompatibilités. Si une valeur RF indispensable ou le matériel manque, refuser l'application complète ; ne pas substituer un autre appareil. Si seule une sortie réseau échoue après application RF, afficher « partiellement appliqué », lister les sorties actives et celles en erreur ; ne pas prétendre à un rollback matériel automatique.

L'enregistrement ne redémarre pas automatiquement au chargement d'un preset. Un état recorder=on sauvegardé reste informatif ; l'opérateur confirme toute nouvelle capture. Un preset peut définir son répertoire et son profil, jamais écraser un fichier existant.

Auto-connect sélectionne uniquement l'identité attendue. Auto-start démarre après validation complète du matériel et des réglages. Les deux options sont indépendantes et désactivées par défaut à une nouvelle installation. Un matériel absent laisse l'application disponible avec erreur visible ; en headless, suivre la politique de tentative configurée et un code de sortie explicite.

## 2. Headless

La CLI conserve les points d'entrée amont lorsqu'ils existent. L'ajout exact des options sera fait dans le module existant ; responsabilités requises : sélectionner un fichier de configuration, source simulée/replay, mode sans GUI et niveau de journalisation.

Codes de sortie proposés : 0 arrêt demandé proprement ; 2 configuration invalide ; 3 source impossible à ouvrir ; 4 erreur fatale de fonctionnement ; 5 ressource réseau indispensable impossible à ouvrir. Une destination facultative en échec ne provoque pas une sortie 5 ; son caractère indispensable doit être configuré explicitement.

Ctrl+C déclenche un arrêt ordonné : empêcher nouvelles commandes/connexions, arrêter le recorder proprement, arrêter émission/pipelines, arrêter la source, fermer lecteurs et mémoire partagée, finaliser les logs. Les threads ne doivent pas rester cachés après retour du processus. Un timeout d'arrêt est enregistré et rend la sortie non propre, sans blocage infini.

La GUI et le headless utilisent la même validation et le même contrôleur. Aucun `QApplication` requis pour recevoir, resampler ou distribuer en headless. L'installation comme service Windows et une GUI déconnectable sont des extensions séparées.

## 3. Watchdog et panne

Détecter l'absence de blocs, pas l'absence de signal RF. Délai initial 2 s, configurable par source pour les matériels à démarrage lent. L'erreur backend explicite déclenche directement la récupération sans attendre le watchdog.

Séquence de reprise proposée : libérer proprement la source, attendre 1/2/5/10/30 s entre cinq tentatives, toujours rechercher la même identité. Chaque tentative est annulable par Stop. Après cinq échecs : ERROR, bouton « Réessayer », aucune boucle infinie. Les clients voient une source indisponible ; le serveur ne leur envoie pas des zéros comme si la réception était réelle.

Une reprise réussie crée une nouvelle époque, revalide les profils de sortie et réinitialise les filtres. Un abonnement devenu incompatible passe en erreur sans invalider ceux encore compatibles. La capture interrompue est close puis une nouvelle capture demande une politique explicitement autorisée ; proposition initiale : ne pas redémarrer automatiquement le recorder.

Surcharge : la file d'un consommateur est bornée. Émetteur/affichage en retard : abandon des éléments les plus anciens et compteurs. Recorder incapable de suivre : arrêter la capture proprement et afficher le motif. Ne pas ralentir le callback matériel pour sauver une destination ou un fichier.

## 4. Recorder et replay

V1 proposée : une capture active d'une source ou d'une sortie de profil explicitement sélectionnée. Le recorder est un consommateur supplémentaire du pipeline existant ; aucune nouvelle chaîne DSP identique pour lui seul.

Cible de stockage : paire SigMF, données et métadonnées. Avant codage du format externe, fixer la version de la spécification officielle et utiliser son validateur lorsqu'il existe. Les clés exactes ne sont pas inventées dans ce document ; le lot doit livrer une capture de référence et sa validation standard.

Le nom est unique ; un fichier existant n'est jamais tronqué sans demande distincte. Les métadonnées décrivent datatype, fréquence d'échantillonnage, fréquence centrale, provenance temporelle et changements/discontinuités documentables. Ne pas écrire une date UTC de capture à partir d'un compteur matériel relatif sans conversion établie.

Un changement de taux/format ou une nouvelle époque clôt la capture courante dans la proposition initiale. Afficher son motif ; ne pas concaténer des octets de formats différents. Rotation par taille/durée : extension configurable à valider ; aucun nettoyage automatique des anciennes captures en V1 initiale.

Disque plein ou erreur d'écriture : désabonner le recorder, conserver les données déjà écrites et les métadonnées récupérables, signaler que la capture est incomplète. Les clients IQ et la GUI restent en service. La file recorder a une limite mémoire et un compteur d'overrun.

Replay : sélectionner les métadonnées et retrouver le fichier de données associé ; refuser longueur non multiple de la taille IQ, type non supporté ou fréquence d'échantillonnage absente. Cadence temps réel par défaut, accélération réservée aux tests hors promesse réseau temps réel. EOF : arrêt du flux, état READY, message « fin de fichier » ; boucle désactivée par défaut. Seek/loop créent une nouvelle époque. Aucun SDR physique ouvert pour un replay.

## 5. Source de test et diagnostic

La simulation doit être reproductible : seed, taux, format, amplitude, fréquence du sinus complexe et taille de bloc explicites. Signaux : sinus ±f, impulsion, bruit déterministe et zéro. Défauts injectables : trou de taille connue, trou inconnu, exception d'acquisition, arrêt de production, changement de configuration et retard d'un consommateur.

Les injections n'agissent pas sur le SDR réel. Les tests de reconnexion emploient un faux backend et une horloge contrôlée. Les essais manuels de débranchement du RSPdx sont distincts et annoncés avant leur exécution.

Export diagnostic : versions application/OS/backend, paramètres non secrets, source et compteurs, erreurs récentes. Exclure tokens, données IQ et informations de connexion privées non nécessaires. Afficher le dossier exporté et sa taille.
