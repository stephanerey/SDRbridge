# S6 — Référence d'exécution v0.3

Date : 13 octobre 2026. Ce complément tranche les choix techniques laissés proposés en v0.2. Il devient le contrat de travail avec le prompt de lancement ; il ne prétend pas être une preuve d'implémentation. Priorité : instruction utilisateur > S6 > S1–S5 > exemples. Le périmètre produit du PRD reste inchangé, sauf qualification QMAP explicitement différée.

## 1. Choix fermés pour le lancement

- V1 : exactement une source active, matérielle OU simulation OU replay ; RX uniquement. Le multi-SDR simultané reste hors V1.
- Python de développement et de livraison Windows : 3.12 x64, environnement isolé du Python ANTRACK. Ne pas remplacer un Python système.
- Soapy générique principal ; backend SDRplay natif conservé comme option de secours, non supprimé en V1. Sélecteur explicite ; pas de bascule silencieuse vers un autre appareil/backend.
- Paramètres P-02 à P-14 de DECISIONS retenus. P-01 remplacé par Python 3.12. Les règles RF de S1, profils immuables et transactions de presets de S5 sont des décisions d'exécution, non des questions à reposer.
- Dépendances autorisées dans le futur environnement du bridge : NumPy 2.5.4, SciPy 1.18.1, PyQt5 5.15.11, PyQtGraph 0.14.0, zeroconf 0.151.5 ; outils PyYAML 6.0.3 et jsonschema 4.26.0. Résolution Windows/Python 3.12 vérifiée par pip en mode simulation, pas compatibilité fonctionnelle prouvée. Figer aussi les dépendances transitives après installation/test. Ne pas ajouter une dépendance différente sans justification.
- Conserver unittest ; tests Qt avec QtTest fourni par PyQt5. Aucun besoin de réécrire toute la suite sous pytest.
- Ne pas présumer que les bindings Python Pothos conviennent à Python 3.12. Étendre le wrapper C existant à l'API Soapy requise, avec signatures vérifiées contre les headers locaux, ou utiliser des bindings dont ABI/interpréteur ont été vérifiés. Aucun chemin vers le Python ANTRACK dans le runtime bridge.
- Nexus absent du chemin critique : SR Core, pas de connexion MCP nécessaire pour coder ou exécuter le produit.

## 2. Organisation du logiciel et contrats internes

Conserver `src/sdr_bridge` et les points d'entrée du paquet. Responsabilités : `app` compose ; `bridge` orchestre ; `model` porte les données immuables ; sources acquièrent ; `ring` distribue ; `control` valide ; `udp` encode/émet. Ajouter des modules `profiles`, `dsp`, `rf_profiles`, `recording`, `config` et une couche Qt seulement lorsque le lot les utilise. Pas de framework parallèle.

Interface source cible : enumerate(), capabilities(device_id), open(device_id), configure(request)->EffectiveConfig, start(on_block,on_error), stop(), close(). Les méthodes de commande sont sérialisées hors callback. Le callback ne touche ni widgets, ni sockets, ni disque ; un tampon borné et son compteur de pertes protègent le producteur. Une exception de thread remonte au contrôleur.

`apply_config(expected_revision, requested)` rejette une révision périmée sans effet. Si un backend ne garantit pas la frontière des échantillons, arrêter le flux, appliquer, relire, créer une époque puis reprendre. Échec : état effectif relu ou ERROR ; jamais annoncer les valeurs demandées comme acquises. Chaque snapshot est immuable et porte source_id, epoch et config_revision.

Simulation : I=amplitude*cos(phase), Q=amplitude*sin(phase), fréquence positive à droite du spectre ; phase continue entre blocs, seed explicite. Les tests fixent seed=1, Fs=2_000_000, bloc=4096, amplitude=0.25, ton=10_000 Hz. Injecter les défauts via faux backend uniquement.

Contrôle historique : maintenir les verbes nécessaires à ANTRACK/ExtIO, mais refuser toute mutation RF provenant d'un client IQ, y compris un ancien token client. Le pilotage GUI/headless est interne au contrôleur, pas un privilège transféré à un abonné.

## 3. Mémoire partagée : migration bornée et explicite

L'audit ne permet pas de certifier le ring v1 : en-têtes non alignés pour toutes les opérations 64 bits, vérification avant copie uniquement, pointeur ExtIO conservé pendant callback. **Ne pas présenter une simple seconde lecture Python comme une preuve d'atomicité.**

Choix de réalisation : ring SDBR v2 distinct, aligné, writer unique, copie lecteur vérifiée par séquence de publication. Conserver un lecteur v1 pour transition ; ne jamais émettre v2 sous un descripteur v1. L'émission v1 reste une option de compatibilité explicitement non qualifiée, désactivée par défaut. Mettre à jour ensemble writer, client Python, shim ANTRACK fourni par ce dépôt et ExtIO fourni par ce dépôt. Ne pas modifier l'installation ANTRACK/HDSDR existante pendant le développement.

Layout cible little-endian ; header fixe 128 octets : magic[4]@0, version u32@4=2, header_bytes u32@8=128, slot_count u32@12, slot_stride u32@16, max_samples u32@20, format u32@24 (1 CS16, 2 CF32), publication_guard u32@28, latest_sequence u64@32, epoch u64@40, réservés zéro jusqu'à 128. Chaque slot commence à un multiple de 64 : guard u32@0, sample_count u32@4, sequence u64@8, first_sample_index u64@16, timestamp_ns u64@24, epoch u64@32, config_revision u32@40, rate u32@44, frequency u64@48, flags u32@56, time_domain u32@60 ; payload@64. stride=align64(64+max_samples*bytes_per_IQ). Les identités textuelles sont dans le descripteur de contrôle. latest_sequence=UINT64_MAX signifie vide, jamais une séquence publiée.

Sous Windows, implémenter les gardes via un petit helper natif C ABI, compilé x64 pour Python et Win32 pour ExtIO. Opérations Interlocked 32 bits alignées et barrières explicites ; pas d'hypothèse sur atomicité de `struct.pack_into` ou du GIL interprocessus. Writer rend guard impair avant toute réécriture, écrit les champs/payload, puis publie guard pair après barrière ; publication du dernier index sous garde séparée. Reader lit une garde paire, copie les champs et le payload dans sa mémoire, vérifie de nouveau garde et séquence avec les barrières requises, rejette la copie si changement. Trois tentatives maximum avant abandon compté, sans bloquer le writer. Toute vue livrée au consommateur est une copie possédée par le lecteur. Les callbacks ExtIO utilisent cette copie.

Premier jalon du lot RING : relire les exigences mémoire Windows/C++, écrire les tests multiprocessus de wrap et compiler le helper aux deux architectures avant de brancher les clients. Si cette stratégie ne permet pas de démontrer la cohérence, arrêter ce sous-lot avec preuve et solution minimale ; ne pas contourner par une assertion de sûreté. C'est une vérification d'ingénierie indispensable, pas une nouvelle discovery produit.

Configuration initiale : 64 slots ×4096 IQ, plafond clients=null (illimité par politique), plafond configurable strictement positif. Admission sous manque de ressources avec erreur explicite. Files : source et chaque pipeline 16 blocs, chaque destination 32, recorder 64, GUI dernier bloc seulement. Documenter la mémoire en fonction des formats ; abandon le plus ancien sauf recorder qui s'arrête. Tests de lecteur suspendu doivent démontrer que les lecteurs sains et le writer continuent.

## 4. DSP : algorithme et oracle

Resampling rationnel polyphase FIR, L=Fs_out/gcd et M=Fs_in/gcd. Concevoir au taux Fs_in*L, coupure médiane 0.45*Fs_out, transition 0.10*Fs_out, fenêtre Kaiser pour le gabarit P-10 ; vérifier numériquement et augmenter le nombre de taps si nécessaire. Gain DC compensé par L. Référence hors ligne : convolution puis décimation avec les mêmes taps ; SciPy `upfirdn` fournit un oracle utile.

L'implémentation streaming conserve l'historique FIR et la phase polyphase : **ne pas appeler indépendamment resample_poly sur chaque bloc**. La concaténation de sorties de partitions différentes du même signal doit correspondre à l'oracle après alignement du retard. Pas de padding répété aux frontières ; amorçage à zéro au début d'époque seulement. Retard de groupe publié en échantillons/secondes ; pas de faux timestamp matériel corrigé sans relation définie.

Calcul interne float64 pour conception/oracle, complex64 pour flux si le gabarit mesuré est respecté. Pas de normalisation automatique, upsampling ni DDC. Bypass à taux/format identiques. Saturation CS16 et non-finis selon S3. Sur trou DSP, réinitialiser le filtre et marquer discontinuité du pipeline, sans créer de fausse nouvelle époque matérielle.

Profils initiaux proposés à l'opérateur : master CS16 au taux source, ANTRACK CS16 192000, ANTRACK CS16 96000, native CF32 192000. N'activer aucun profil incompatible ; ne pas ramener silencieusement son taux. Mesurer filtre flottant hors effets de quantification ; mesurer séparément l'erreur CS16.

## 5. Réseau et compatibilité

S4 fixe le contrôle natif JSON API1 et les données UDP wire2 (versions indépendantes) ; ne pas transmettre leurs headers à SDR++. Les réponses TCP possèdent request_id, ok et result OU error={code,message}. Conserver exactement les codes d'erreur de S4. Pas de trace Python ni secret dans l'erreur distante.

JSON par ligne, 65536 octets maximum avec terminaison ; refuser NaN/Infinity, clés dupliquées, profondeur >16, champs inconnus dans les commandes. Enveloppe : api_version=1, request_id chaîne 1–64 caractères, method, params objet. `hello` params={client_name,client_version,token} ; résultat={client_id,run_id,role:"read",heartbeat_interval_s:5,lease_timeout_s:15}. Token jamais renvoyé. Les autres commandes exigent hello réussi sur la connexion courante. Entiers64 sémantiques encodés en chaînes décimales comme S4.

`subscribe` params={source_id,profile_id,profile_revision,transport:"udp_unicast",port} ; adresse déduite du pair, port entier 1024–65535. Résultat={subscription_id,wire_stream_id,epoch,profile_id,profile_revision,endpoint:{host,port},effective:{sample_rate_sps,sample_format,center_frequency_hz,config_revision}}. `unsubscribe` params={subscription_id}, idempotent pour une souscription de ce client déjà libérée. `get_status`, `list_sources`, `list_profiles`, `goodbye` : params={}. `heartbeat` : params={} ou telemetry bornée <=16 champs scalaires, chaque chaîne <=128 caractères ; ne jamais considérer ses chiffres comme mesures serveur. Un client ne peut lire les jetons ni supprimer l'abonnement d'un autre. Multicast et destinations statiques sont créés par l'opérateur seulement.

Les réponses list_sources/list_profiles renvoient les objets S2 sous `items`; get_status retourne état source, configuration effective, compteurs et les abonnements du client appelant. Aucun verbe distant de configuration RF. Une nouvelle connexion crée une nouvelle session ; aucune récupération implicite d'un ancien abonnement. Souscriptions purgées à la déconnexion ou au timeout. Un heartbeat est une présence, pas un nombre de blocs IQ lus.

Jeton LAN : secret aléatoire >=32 octets, stocké par l'opérateur dans un fichier local hors dépôt, indiqué par référence. Le protocole TCP n'est pas chiffré ; usage LAN de confiance/VPN uniquement, jamais Internet. Pas de jeton dans mDNS. Pas d'ouverture de pare-feu automatique. Listener natif désactivé par défaut ; activer loopback pour les tests. Réseau LAN et interfaces choisies réclament autorisation séparée.

**SDR++ 1.2.1 :** adapter raw UDP CS16 little-endian sans header, module Network Source, paramètres d'échantillonnage et fréquence renseignés côté SDR++ ; profil de transport distinct `sdrpp_raw_cs16`. Budget1200 octets donc300 IQ/datagramme. Le client tiers ne reçoit pas les époques/pertes du protocole natif : limitation documentée, pas de comptage réception inventé. Qualification manuelle requise avec la version installée. Le code officiel actuel du module confirme ce format ; cela n'atteste pas encore le binaire installé.

**ANTRACK :** conserver l'API publique du shim, éliminer interpolation linéaire/FIFO illimitée, consommer le profil DSP partagé correspondant au taux demandé. Lire les métadonnées effectives après changement ; setters clients sans autorité, refus explicite là où l'API l'autorise. Validation sur copie isolée du commit distant épinglé, pas sur le dossier local sale.

**HDSDR :** ExtIO Win32, callbacks et buffers possédés, fréquence/taux effectifs actualisés et notifications ExtIO appropriées. Ne pas copier une DLL dans l'installation existante sans autorisation.

**QMAP :** version/interface non identifiées ; pas d'adaptateur inventé. Reste une extension de qualification différée, explicitement visible dans la matrice. Ce point ne bloque pas la réalisation du reste de V1, mais interdit l'étiquette « QMAP compatible ».

## 6. Persistance, capture et replay

Racine configuration : `%LOCALAPPDATA%/SDRbridge`, remplaçable par `--config PATH`. Schéma JSON version1 ; app.json, presets/*.json et window.json séparés. Valeurs par défaut : source simulée, réseau désactivé, auto-connect=false, auto-start=false, recorder arrêté. Le lot OPS livre les schémas JSON, un exemple valide et les tests de round-trip, version inconnue, fichier corrompu et écriture interrompue. Aucun remplacement automatique d'un fichier invalide.

CLI : conserver les options amont compatibles ; ajouter `--config`, `--headless`, `--source simulated|soapy|native|replay`, `--replay PATH`, `--log-level`, sans casser les entrées existantes. Une option fournie prime sur le fichier, le fichier prime sur les defaults. `--source replay` exige --replay ou un chemin valide en configuration. Source simulée n'ouvre aucun SDR.

SigMF **1.2.6** figé : données `.sigmf-data` et JSON `.sigmf-meta` de même base, nom créé exclusivement, jamais écrasé. `global` contient core:version="1.2.6", core:datatype="ci16_le" ou "cf32_le", core:sample_rate, core:num_channels=1, core:recorder="SDRbridge" ; `captures` contient core:sample_start=0 et core:frequency effectif ; `annotations`=[] au minimum. Omettre core:datetime sans UTC capture fiable. Ne pas utiliser core:dataset pour une paire standard. Métadonnées d'interruption dans core:description en texte, pas de clés d'extension non spécifiées.

Le recorder s'arrête à toute discontinuité de son entrée (pas seulement nouvelle époque) : aucune concaténation cachée de trous. Finaliser les métadonnées atomiquement et le nombre réel d'octets écrits ; tronquer uniquement une queue d'échantillon partiel du fichier que ce recorder vient de créer si nécessaire. Disque plein : conserver le récupérable, signaler incomplet, pas de redémarrage automatique. Valider le JSON avec le schéma officiel épinglé, et séparément les invariants binaires car le schéma ne lit pas le fichier IQ.

Replay V1 accepte seulement une paire monovoie ci16_le/cf32_le, sample_rate entier positif, première capture sample_start=0, fréquence connue, sans headers/trailers ni offsets de données non pris en charge. Pour plusieurs captures ou métadonnées de segments, refuser explicitement tant que leurs changements ne sont pas implémentés ; ne pas les ignorer. Seek en index IQ, borné à la taille réelle, boucle=false, EOF=READY ; changement de position crée une époque.

## 7. Seuils de recette et limites de l'autonomie

Recette simulée : source2MS/s CS16, profils192/96k, cinq lecteurs locaux, deux UDP loopback, GUI active. Test fonctionnel10min puis endurance60min. Exiger zéro bloc déchiré accepté, zéro perte des consommateurs rapides en régime nominal sur la machine de référence, aucune file au-delà de sa borne, arrêt <=5s. Après échauffement5min, croissance mémoire privée <=64MiB sur l'heure ; cible mémoire processus <=512MiB et CPU moyen <=25% de la capacité machine totale. Ces valeurs sont des critères à mesurer, **pas des performances déjà obtenues**. En dépassement, profiler et proposer la correction ; ne pas abaisser le seuil silencieusement.

La latence end-to-end se mesure par injection corrélée, pas en soustrayant des horloges non reliées. Objectif p95 <=250ms sur parcours loopback192k ; publier méthode, nombre de mesures et p99 observé. Matériel/clients réels : essais distincts après autorisation, aucune revendication issue des seules simulations.

Les bibliothèques autorisées, migration ring versionnée et schémas de fichiers neufs font partie du périmètre du prompt. Aucun droit implicite à modifier un pilote, installer des logiciels système, changer ANTRACK, publier, indexer chez OVH ou activer le SDR. Les blocages de recette n'interrompent pas les lots indépendants ; la livraison reste `user_testing` tant que les preuves réelles manquent.

## Sources de contrats externes

- [SigMF 1.2.6 et schéma](https://github.com/sigmf/SigMF/tree/v1.2.6), commit `418d9170c287ebd378122d65426b38b62a43ecf5`.
- [Module officiel SDR++ Network Source](https://github.com/AlexandreRouma/SDRPlusPlus/blob/master/source_modules/network_source/src/main.cpp), observation du13/10/2026 ; vérifier le module installé en recette.
- Versions de dépendances vérifiées via métadonnées PyPI et résolution pip locale ; voir le rapport de préparation.
