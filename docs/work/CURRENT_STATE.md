# État réel — SDRbridge 0.6.1 publiée — 10 novembre 2026

## Implémenté

- Cœur RX mono-source par processus, ring SDBR v2, transport SDBU v2, profils DSP, capture/replay SigMF et contrôle local.
- Connecteurs SDR++ 1.3.0 x64, ExtIO HDSDR Win32 et shim ANTRACK, tous en lecture seule côté RF.
- Journaux JSON persistants et rotatifs, fichier de fautes natives, `run_id`, métriques de file/dispatcher et chemin visible dans Diagnostics.
- Backend Soapy générique intégré au paquet Windows via la couche ctypes, avec catalogue filtré par backend, modèle et numéro de série.
- Inventaire réel : RSPdx `2001077942`, clone RSP1 `0000000001` et backend MSi2500 ; les périphériques audio Pothos sont exclus.
- Instances nommées : configuration, logs et rings isolés ; `--port-offset` décale les ports de contrôle et UDP ; `--device-id` sélectionne explicitement le récepteur.
- Interface Qt 0.6.0 affichant la source effective, le nom de l'instance et les paramètres de chaque destination UDP.
- Icône SDRbridge dédiée, lisible de 16×16 à 256×256, appliquée à l'exécutable, aux fenêtres Qt, à la barre des tâches, aux raccourcis et à l'installeur ; l'identifiant d'application Windows stabilise aussi l'icône épinglée.
- Paquet portable et installateur construits à partir de la version de `pyproject.toml`, avec aide, licences et connecteurs inclus.
- Transport QMAP 0.6/Linrad UDP RX : resampling mutualisé 96 kS/s, trames fixes 1416 octets, fréquence centrale et convention spectrale QMAP ; coexistence configurée avec SDR++.
- Distribution 0.6.0 construite sous `release-v0.6` avec Inno Setup 6.7.3.
- Source fichier IQ WAV/RF64 HDSDR/SDR++ : I/Q stéréo `uint8`, `int16`, `int32` ou `float32`, lecture temps réel, boucle optionnelle et fréquence centrale issue du nom ou d'une surcharge.
- Sélection graphique du fichier dans la liste des sources, remplacement à chaud et retour au SDR sans recréer le bridge ni ses destinations.
- Destinations UDP à débit indépendant, configurables dans l'interface avec taille de datagramme et profondeur de file ; les traitements DSP identiques sont mutualisés.
- Optimisation du chemin plein débit CS16 sans conversion flottante et pacing SDR++ sans attente active.
- Captures au choix en SigMF 1.2.6, SDR++ WAV int16 stéréo ou HDSDR WAV int16 stéréo avec chunk `auxi`; boîte Windows **Enregistrer sous** ouverte dans `C:\Projets\SDRBridge\Captures`.
- Séquence de publication SDBR monotone pendant toute la vie des rings master et profil : Stop/Play, fichier vers SDR, seek et récupération ne bloquent plus les lecteurs déjà attachés. L'époque et `first_sample_index` conservent les frontières de continuité.
- Interface Qt v0.7 sombre à barre Windows native : quatre onglets opérateur, ruban de métriques, modes Spectrum/Waterfall/Split synchronisés avec le compact 396×112, diagnostics en fenêtre modale et langue Français/English sélectionnable.
- Dans l’onglet Radio, les réglages matériels précèdent désormais le VFO, lui-même placé juste au-dessus de l’analyse RF. Les axes gauches Spectrum/Waterfall ont une largeur commune et leurs fenêtres fréquentielles sont appliquées ensemble après la transformation de l’image, ce qui aligne exactement les fréquences en mode Split.
- Le ruban supérieur expose la charge CPU du seul processus SDRbridge sous la forme `cœurs logiques utilisés / disponibles`, sans pourcentage ambigu. Les mêmes valeurs et le nombre de processeurs logiques sont disponibles dans Diagnostics.
- Profils RF persistants et opérationnels : plages, priorité, périphérique, antenne, AGC, gains IF/RF, bande passante, activation et hystérésis ; le profil actif suit la fréquence et peut être suspendu manuellement.
- Vue Clients & Streams unifiée : consommateurs locaux et destinations UDP sont comptés ensemble, avec débits IQ logique/UDP, débit réseau mesuré, datagrammes, files et pertes.
- L’ExtIO est un consommateur local du ring maître : contrôle sur `127.0.0.1:47631`, IQ `CS16` en mémoire partagée, aucun port UDP et aucun profil décimé. Chaque instance reçoit le débit source complet, contribue au débit IQ logique mais pas aux métriques UDP. HDSDR 2.81a et SDRuno 1.42.1710 via `SDRuno.EXTIO.exe` sont certifiés ; les autres hôtes Win32 restent non qualifiés.
- La couche Soapy lit aussi `getSampleRateRange`/`getBandwidthRange` et le readback AGC, antenne et gains. La GUI construit les deux contrôles RSP1A `IFGR`/`RFGR` depuis les capacités, les présente comme réductions et inverse leur sens visuel ; les réglages matériels sont verrouillés pour une source fichier.
- La bande passante est le filtre tuner/IF matériel exposé par Soapy, distinct du débit IQ. Le mode **Auto**, actif par défaut et mémorisé, sélectionne le filtre disponible le plus proche du débit demandé sans éliminer les filtres plus larges ; toutes les valeurs matérielles restent proposées manuellement. Le rafraîchissement à 1 Hz respecte désormais les modifications encore dans la temporisation d'application.
- La vue compacte affiche directement la fréquence sans marque ni état RX redondant. Sa commande Play/Stop permet l'arrêt et le redémarrage ; elle est grise à l'arrêt, ambre pendant la commande asynchrone et verte seulement en RUNNING, comme la commande de la vue normale.
- Waterfall est le mode RF initial. Si l'inventaire matériel manque lors du premier rendu, la GUI relit automatiquement les capacités au lieu de laisser les contrôles vides ; la fermeture affiche explicitement son attente pendant la libération SDRplay.
- La bascule Français/English retraduit immédiatement les quatre onglets, métriques, réglages Radio, axes RF, tables et éditeur UDP, profils RF, captures, diagnostics, boîtes modales, textes dynamiques et vue compacte ; les libellés ne reviennent plus à l'anglais lors du rafraîchissement à 1 Hz.
- Deux curseurs dBFS étroits sont empilés verticalement à droite de l’analyse RF normale, Max au-dessus de Min, sans valeurs numériques ni titre supplémentaire. Ils règlent uniquement l’échelle du spectre et les niveaux de couleur de la cascade ; le remplissage spectral descend toujours jusqu’à la borne Min, sans découpe, et aucun gain SDR n’est modifié.
- Les axes X des vues normales Spectre, Cascade et Partagé affichent la fréquence absolue en MHz à quatre décimales, obtenue par `VFO effectif + offset FFT`. La vue compacte conserve ses axes masqués et cette conversion reste strictement visuelle.
- La journalisation SDRbridge est attachée à son logger de paquet et non plus au logger racine que Qt/Soapy peut reconfigurer. Le chemin fractionnaire critique 10→4 MS/s utilise un préfiltre elliptique et un FIR court de 19 taps au lieu du FIR monolithique de 509 taps.
- À partir de 8 MS/s, les profils forment une cascade mutualisée dont chaque étage possède une file bornée et un worker persistant. Par exemple, QMAP 96 kS/s réutilise la sortie 4 MS/s (`10→4→0,096`) au lieu de refaire le filtrage depuis 10 MS/s ; les étages peuvent être planifiés sur plusieurs cœurs sans bloquer le dispatcher central.
- La réception Soapy demande le format natif CS16. Le dispatcher écrit le ring maître et alimente une file DSP dédiée sans attendre le rééchantillonnage des clients ; les pertes et temps des deux étages sont exposés séparément. Les blocs par défaut sont de 32768 échantillons et le débit mesuré est recalculé toutes les 500 ms.
- Un retour Soapy `OVERFLOW` n'arrête plus l'acquisition : il crée une discontinuité `SOURCE_LOSS`, réinitialise l'index d'échantillon et incrémente les pertes source, puis la lecture continue. Le journal `SOAPY_RX_OVERFLOW` est limité à une entrée toutes les cinq secondes.
- Les destinations UDP LAN disposent d'une autorisation sortante dédiée, persistante et activable dans **Settings**, sans ouvrir le contrôle RF natif. La saisie d'une adresse distante remplace automatiquement le budget loopback de 8192 octets par 1200 octets. Les README et l'aide intégrée documentent aussi explicitement l'assistance IA et l'usage de la SR Method 4.1 d'Auroramind.

## Preuves obtenues

- 48/48 tests applicatifs verts.
- 51/51 tests applicatifs verts après ajout QMAP, dont vecteur de trame, agrégation, frontière de discontinuité et réception UDP intégrée à partir d'une source 2 MS/s simulée.
- 60/60 tests applicatifs verts, dont démarrage en découverte sans SDR, sélection graphique avec lecture automatique, permutation SDR/fichier, lecture de vecteurs WAV et réception simultanée vérifiée à 2 MS/s, 192 kS/s et 1 MS/s.
- 63/63 tests applicatifs verts après ajout des deux formats WAV et du dialogue natif de sauvegarde.
- 65/65 tests applicatifs verts après réparation Stop/Play et permutation fichier vers SDR, avec lecteurs master et profil rééchantillonné conservés et restauration visuelle de la source effective en cas de rejet.
- 68/68 tests applicatifs verts après refonte GUI v0.7, dont Waterfall/Split, synchronisation de la vue compacte, compteur local+UDP et sérialisation/hystérésis des profils RF.
- Rendu Qt automatisé vérifié en 1280×800 et en compact 396×112 ; le producteur simulé continue de 522 à 644 blocs pendant la bascule de présentation.
- 73/73 tests applicatifs verts après corrections opérateur RSP1A : plages Soapy, readback IFGR/RFGR, inversion des réductions, verrouillage fichier, couleurs de fréquence et bouton d'acquisition.
- 74/74 tests applicatifs verts après passage asynchrone du Play/Stop et validation du cycle arrêt-redémarrage depuis la vue compacte.
- 75/75 tests applicatifs verts avec Waterfall par défaut et chargement automatique des capacités. Sonde réelle RSP1A : 19 débits, 8 bandes passantes, RX, IFGR 20–59, RFGR 0–9 et AGC ; écriture/relecture matérielle validée à 1 296,3 MHz, 2 MS/s, 1,536 MHz, IFGR 40 et RFGR 0.
- 76/76 tests applicatifs verts après ajout d'une régression de bascule Français → English couvrant les onglets, réglages, graphes, tables, captures, diagnostics, vue compacte et textes recalculés. Rendu Qt français des quatre onglets et du compact généré en 1280×800 / 396×112 ; le flux simulé progresse de 524 à 646 blocs pendant la bascule de vue.
- 77/77 tests applicatifs verts après restauration des curseurs d’échelle RF : visibilité en vue normale, axe spectral et niveaux de cascade contrôlés ensemble, réception simulée continue. Rendu français 1280×800 et compact 396×112 ; le producteur progresse de 564 à 685 blocs pendant la bascule.
- 78/78 tests applicatifs verts après passage aux axes absolus : à 144,735 MHz, les offsets −2,5/0/+2,5 kHz s’affichent 144.7325/144.7350/144.7375 MHz et le changement de VFO met à jour les quatre axes normaux. Rendu français 1280×800 ; le producteur simulé progresse de 554 à 676 blocs pendant la bascule compacte.
- 78/78 tests applicatifs toujours verts après correction de l’échelle : une borne Min à −135 dBFS déplace aussi le niveau de remplissage à −135 dBFS, les curseurs Max/Min sont alignés dans une colonne, et la réception continue. Rendu français Spectre/Cascade 1280×800 ; progression simulée de 528 à 651 blocs.
- 84/84 tests applicatifs verts après isolation du journal, réception CS16 directe et séparation dispatcher/DSP. Smoke RSP1A réel avec sorties SDR++ 2 MS/s et QMAP 96 kS/s : 8 MS/s maintenus plus d'une minute puis 10 MS/s près de deux minutes dans la GUI Split, trois consommateurs actifs, débit mesuré respectivement 7,999 et 10,064 MS/s, zéro perte source/DSP/UDP. Le rendu FFT/cascade ne traite plus les vues cachées et plafonne la cascade à 1024 colonnes.
- 86/86 tests applicatifs verts après optimisation 10→4 MS/s et parallélisation par profil. Smoke RSP1A réel prolongé plus de trois minutes à 10 MS/s avec GUI 10 MS/s, SDR++/SDBU 4 MS/s et QMAP 96 kS/s : environ 432 000 datagrammes 4 MS/s transmis, zéro perte source/DSP/profil/UDP et zéro erreur. Charge mesurée sur l'i5-9500 : 34,3 % machine, soit 2,06 cœurs effectifs, avec deux workers principaux à 0,73 et 0,59 cœur.
- 86/86 tests applicatifs toujours verts après ajout de la bande passante Auto. Validation RSP1A réelle : 4 MS/s applique automatiquement 5 MHz et mesure 4,062 MS/s ; 10 MS/s applique 8 MHz, mesure 10,064 MS/s et conserve zéro perte. Les huit filtres matériels 0,2/0,3/0,6/1,536/5/6/7/8 MHz restent sélectionnables manuellement.
- 87/87 tests applicatifs verts après réorganisation Radio, alignement Spectrum/Waterfall et métrique CPU processus. Validation visuelle native à 2 MS/s avec trois consommateurs : graduations fréquentielles superposées, environ 0,72 à 1,23 cœur utilisé selon l’activité de rendu, zéro perte.
- 88/88 tests applicatifs verts après ajout de la reprise sur débordement Soapy. Une qualification RSP1A prolongée à 10 MS/s avec sorties SDR++ 2 MS/s et QMAP 96 kS/s a tenu environ dix minutes à 10,064 MS/s, zéro perte et environ 2,22 cœurs logiques utilisés ; Stop/Play et fichier HDSDR vers RSP1A ont aussi repris correctement.
- 90/90 tests applicatifs verts après ajout de l'export diagnostic, de la pile de livraison et du pipeline DSP en cascade multicœur. Qualification RSP1A réelle de 60 s avec le runtime privé SoapySDR 0.9 / SoapySDRPlay3 0.5.2, source 10 MS/s, sortie SDBU 4 MS/s et QMAP 96 kS/s : 10,064 MS/s mesurés, zéro perte source, zéro drop DSP/profil et zéro erreur.
- 91/91 tests applicatifs verts en 0.6.1, dont le chargement de l'icône Qt globale. L'icône extraite de l'exécutable et de l'installeur correspond au master multi-résolution ; installation isolée, lancement `--version` et désinstallation terminent avec le code 0.
- 93/93 tests applicatifs verts après séparation de l'autorisation UDP LAN et du contrôle réseau natif, persistance immédiate du réglage et bascule automatique du datagramme distant à 1200 octets.
- Distribution portable et installateur 0.6.0 finaux construits. Installation silencieuse dans un dossier isolé, chargement du runtime Soapy privé et désinstallation réussis avec les codes 0 ; aucune copie de `sdrplay_api.dll` n'est redistribuée. SHA-256 de l'installateur final : `82DF0435C88B200D3E59A654EDA3A936F075921C2BC18F7CDE068B51F24310F7`.
- HDSDR 2.81a installé sur la session réelle avec le dernier build Win32 `ExtIO_SDR_Bridge.dll` : chargement automatique, ring local actif, 2 MS/s affichés et spectrum/waterfall alimentés. La connexion observée est `127.0.0.1:<port éphémère> → 127.0.0.1:47631`; aucun endpoint UDP `7356` n’est utilisé.
- SDRuno final 1.42.1710 installé depuis le paquet officiel signé SDRPLAY LIMITED sans modifier l’API 3.15 existante. `SDRuno.EXTIO.exe` charge la même DLL Win32 depuis son dossier programme, affiche `In SR: 2000000`, passe de PLAY à STOP, alimente SP1 et ouvre une seconde connexion locale indépendante vers `127.0.0.1:47631` simultanément avec HDSDR.
- Recette visuelle archivée dans `docs/TECHNICAL_OVERVIEW.md` : HDSDR, SDRuno, SDR++ et QMAP simultanés, six consommateurs, 323,1 Mb/s IQ logiques, 131,1 Mb/s UDP utiles, environ 130 Mb/s mesurés, 0,38–1,02 cœur SDRbridge sur 6 et zéro perte globale. Les quatre onglets, la vue compacte, les diagnostics et l’aide sont illustrés par des captures réelles.
- Capture SDR++ WAV créée depuis l'interface simulée à 2 MS/s : PCM int16 stéréo, 144 300 000 Hz extrait du nom, 11 026 432 échantillons relus par le lecteur WAV de SDRbridge.
- Smoke du paquet 0.5.0 vert avec le RSP1A `2236027C98` : datagramme QMAP de 1416 octets, centre 144,3 MHz, `nrx=1`, données IQ non nulles.
- Chaque SDR reçoit seul via Soapy à environ 1,92 MS/s, sans drop ni erreur.
- Deux processus simultanés sont verts avec le RSPdx natif (≈1,910 MS/s) et le RSP1 Soapy (≈1,934 MS/s), zéro drop/erreur sur 10 s.
- Le paquet portable énumère les deux séries physiques et termine proprement en mode CLI sans console.
- L'installateur v0.4.0 a été installé dans un dossier isolé, son exécutable chargé, les connecteurs SDR++/HDSDR vérifiés, puis il a été désinstallé sans reste.
- SHA-256 installateur : `7FD9131EB4C0EC467C22B7EE288BFA514CBE9EDC6C300DA61C5DF93C4DDC2FFB`.
- Le smoke de l'installation réelle ouvre la GUI Soapy, affiche le titre v0.4.0, puis s'arrête proprement avec le code 0 ; le conflit entre Qt embarqué 5.15.2 et Pothos Qt 5.15.3 est corrigé par l'ordre d'initialisation.

## Réserves explicites

- Les anciennes réserves Pothos/SDRplay 3.07 sont levées pour SDRbridge : la distribution embarque un ensemble cohérent SoapySDR 0.9 + SoapySDRPlay3 0.5.2, construit proprement contre l'API SDRplay 3.15. Cette pile reste privée à l'application.
- Aucune clé RTL2832 réelle ni USRP B100 n'a encore été qualifié. Leur compatibilité dépend du module Soapy correspondant (`rtlsdr` ou `uhd`).
- L'installateur 0.6.1 n'est pas signé ; Windows peut afficher un avertissement SmartScreen.
- Le gate historique d'endurance reste ouvert : le run simulé final de 10 minutes a produit des drops tardifs, donc le run 60 minutes n'a pas été lancé.
- La source fichier 0.6.0 est validée sur trois enregistrements HDSDR réels int16 à 2 MS/s et sur des vecteurs SDR++ générés ; un enregistrement SDR++ réel reste à rejouer avant publication.
- Les writers WAV suivent les contrats binaires HDSDR/SpectraVue et SDR++ et sont relus par SDRbridge ; leur lecture dans les applications tierces elles-mêmes reste à qualifier. Le RIFF/WAV classique est limité à 4 Gio.
- L'installateur 0.6.1 n'est pas signé numériquement ; SmartScreen peut donc avertir l'utilisateur.
- La refonte v0.7 et la cohérence linguistique sont validées hors écran ; la recette native Windows/DPI reste à faire avant gel graphique.

## Reprise

1. Tester une clé RTL2832 réelle via SoapyRTLSDR, puis l'USRP B100 via UHD/Soapy.
2. Exécuter la recette utilisateur finale sur l'installation isolée, notamment lecture/capture avec SDR++, HDSDR, QMAP et reprise Stop/Play.
3. Lancer ensuite l'endurance longue avant la prochaine version.
4. Pour chaque prochaine version, reconstruire et requalifier l'installateur avant de le joindre à la release GitHub correspondante.
5. Valider visuellement QMAP 0.6 avec **Monitor** actif sur le port 50004 et le RSP1A réel.
