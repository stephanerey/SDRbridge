# Historique des versions

## 0.6.0 — publiée le 10 novembre 2026

- source fichier IQ WAV/RF64 pour les enregistrements HDSDR et SDR++, en stéréo I/Q `uint8`, `int16`, `int32` ou `float32` ;
- capture sélectionnable en SigMF 1.2.6, SDR++ WAV int16 ou HDSDR WAV int16 avec chunk `auxi`, via la boîte Windows **Enregistrer sous** dans le dossier `Captures` ;
- sélection du fichier par l'explorateur Windows depuis la liste des sources, démarrage automatique de la lecture, boucle optionnelle et retour au SDR sans relancer l'application ;
- démarrage de l'interface en mode découverte même lorsqu'aucun SDR n'est encore connecté ;
- identification visible de la source fichier, lecture temps réel, boucle optionnelle et fréquence centrale extraite du bloc HDSDR `auxi`, du nom ou explicitement configurée ;
- débit de sortie indépendant par destination UDP, sans suréchantillonnage, avec pipeline de rééchantillonnage mutualisé entre destinations équivalentes ;
- ajout et modification dans l'interface du débit, de la taille des datagrammes et de la profondeur de file de chaque destination ;
- datagrammes loopback de 8192 octets par défaut, maintien de 1200 octets sur le LAN et paramètres QMAP fixes à 96 kS/s / 1416 octets ;
- chemin direct sans conversion `CS16 -> complex64 -> CS16` pour les sorties au débit source et suppression de l'attente active du pacing SDR++ ;
- blocs de traitement Soapy, natifs et fichier portés à 32768 échantillons par défaut : à 10 MS/s, ce dimensionnement amortit le coût DSP tout en gardant environ 3,3 ms de granularité ;
- Stop/Play, changement fichier/SDR et reprise après erreur conservent une séquence de publication monotone dans les rings persistants ; les lecteurs déjà connectés reprennent immédiatement ;
- interface Qt sombre v0.7 à barre Windows native, quatre onglets, ruban de métriques, diagnostics modal et mode compact 396×112 ;
- onglet Radio réordonné avec les réglages matériels en premier, puis le VFO entre le matériel et l’analyse RF ; en vue partagée, les marges verticales et les plages fréquentielles du spectre et de la cascade sont identiques afin d’aligner exactement les graduations ;
- métrique « SDRbridge CPU » dans le ruban supérieur, calculée uniquement à partir du temps processeur du processus courant et affichée directement en cœurs logiques utilisés / disponibles, sans pourcentage ambigu ;
- affichage RF en Spectrum, Waterfall ou Split, synchronisé entre les vues normale et compacte ;
- restauration en vue normale des curseurs Min/Max d’échelle d’affichage dBFS, empilés verticalement comme dans l’ancienne interface, sans titre ni valeurs numériques ; le remplissage du spectre suit toujours la borne Min et les niveaux pilotent aussi la cascade sans toucher aux gains matériels ;
- axes X absolus en MHz dans les vues normales Spectre, Cascade et Partagé, calculés à partir de la fréquence VFO effective et arrondis à quatre décimales ;
- profils RF persistants et exécutables avec priorité, hystérésis, antenne, AGC, gains et bande passante ;
- langue Français/English sélectionnable depuis les paramètres, avec retraduction immédiate et complète des quatre onglets, tableaux, graphes, boîtes modales, états dynamiques et vue compacte ; compteur de consommateurs corrigé pour inclure les destinations UDP ;
- capacités Soapy complétées par les API de plages et le readback des contrôles ; IFGR/RFGR du RSP1A construits dynamiquement et affichés comme réductions inversées ; réglages RF verrouillés pour les fichiers IQ ;
- bande passante matérielle en mode **Auto** par défaut : la GUI choisit le filtre tuner/IF exposé par le SDR le plus proche du débit IQ (RSP1A : 4 MS/s → 5 MHz, 10 MS/s → 8 MHz), tout en laissant accessibles toutes les valeurs matérielles en sélection manuelle ; la validation n'impose plus artificiellement `bande passante <= débit` ;
- fenêtre About créditant Stephane REY F1TJJ et Philippe Borghini F5JWF ;
- vue compacte allégée autour de la fréquence et commande Play/Stop bidirectionnelle ; les boutons normal et compact passent par un état ambre non bloquant pendant les démarrages SDR lents, puis vert uniquement quand le flux est actif ;
- Waterfall seul sélectionné par défaut ; l'inventaire matériel est relu automatiquement lorsqu'il est absent au premier affichage afin d'exposer débit, bande passante, antenne, IFGR, RFGR et AGC sans action manuelle ;
- fermeture rendue visible avec un état d'attente et un curseur occupé pendant la libération du SDRplay ;
- journalisation applicative isolée du logger racine afin que le chargement de Qt/Soapy ne puisse plus détacher le fichier persistant ; nom de composant stable aussi en lancement `python -m` ;
- chemin DSP haut débit réécrit : la conversion fractionnaire 10→4 MS/s utilise un préfiltre elliptique et un FIR court (19 taps au lieu de 509) ; à partir de 8 MS/s, les profils sont organisés en cascade mutualisée et chaque étage dispose de son worker borné (par exemple 10→4 MS/s puis 4 MS/s→96 kS/s), afin d'exploiter plusieurs cœurs sans recalculer le filtre amont ni bloquer l'acquisition ;
- réception Soapy demandée directement en CS16, dispatcher du ring maître séparé du worker DSP, files et temps DSP visibles dans Diagnostics ; le débit mesuré utilise désormais une fenêtre courte au lieu d'une moyenne depuis le démarrage et le ruban affiche toutes les pertes réelles sous « Total losses » ;
- rendu RF découplé du débit source : la FFT ne convertit que sa fenêtre utile, les graphes masqués ne sont plus redessinés, la cascade est plafonnée à 1024 colonnes avec conservation des crêtes et l'affichage est rafraîchi à 10 Hz ;
- ouverture SDRplay fiabilisée en réutilisant l'enregistrement de découverte au lieu d'enchaîner trois énumérations natives ;
- les modifications de débit/bande passante ne peuvent plus être annulées par le rafraîchissement périodique pendant les 180 ms de temporisation d'application ;
- les pertes des files DSP propres aux profils sont incluses dans « Total losses » et dans le journal d'arrêt ;
- un `OVERFLOW` Soapy est traité comme une perte source récupérable et visible, sans arrêter le récepteur ;
- runtime Soapy privé et reproductible : SoapySDR 0.9.0 + SoapySDRPlay3 0.5.2 construits ensemble contre l'API SDRplay officielle 3.15, sans dépendance à PothosSDR ni redistribution de `sdrplay_api.dll` ;
- licence GPL-3.0-or-later, auteurs, notices des composants tiers, aide bilingue intégrée, export ZIP de diagnostic assaini et installateur Inno Setup bilingue ;
- 90 tests applicatifs verts, plus une qualification RSP1A réelle de 60 s à 10 MS/s avec sorties simultanées 4 MS/s et QMAP 96 kS/s : 10,064 MS/s mesurés et zéro perte source/DSP/profil.

## 0.5.0 — publiée le 31 octobre 2026

- transport QMAP 0.6 compatible avec l'entrée Linrad UDP sur le port 50004 ;
- profil DSP séparé `qmap-linrad-96k`, resampling filtré vers 96 kS/s et trames fixes de 1416 octets ;
- correction de convention spectrale QMAP `(-1)^n * conj(I+jQ)` ;
- destinations UDP configurables individuellement afin de servir simultanément SDR++ et QMAP ;
- sélection du transport QMAP dans l'interface et métriques de destination ;
- 51 tests applicatifs verts et smoke matériel RSP1A avec données IQ QMAP non nulles ;
- paquet portable 0.5.0 vérifié ; l'installateur graphique n'est pas produit sur la machine de build faute d'Inno Setup.

## 0.4.0 — publiée le 15 octobre 2026

- catalogue SoapySDR filtré avec modèle et numéro de série dans la liste des sources ;
- couche ctypes Soapy intégrée au paquet, avec PothosSDR comme runtime externe ;
- instances nommées avec configuration, ports et journaux isolés ;
- sélection matérielle explicite par `--device-id` et décalage de ports par `--port-offset` ;
- inventaire reproductible des récepteurs par `--source soapy --list-devices` ;
- journaux persistants rotatifs et diagnostic des arrêts/crashs ;
- smoke RX matériel reproductible, séparé puis simultané ;
- validation du RSPdx natif et du clone RSP1 Soapy en deux processus simultanés ;
- version de l’application et du packaging portée à 0.4.0.
- raccourcis installés configurés pour ouvrir directement le catalogue Soapy, RX arrêté.
- initialisation du Qt embarqué avant Pothos/Soapy afin d'éviter le conflit Qt 5.15.2/5.15.3 au démarrage installé.

## 0.3.0 — publiée

- cœur RX mono-source, SDBR v2 et SDBU v2 ;
- connecteurs SDR++ et HDSDR ;
- backend SDRplay natif, GUI Qt, profils DSP, capture/replay SigMF et packaging Windows.
