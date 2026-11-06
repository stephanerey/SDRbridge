# Historique des versions

## 0.6.0 — en développement

- source fichier IQ WAV/RF64 pour les enregistrements HDSDR et SDR++, en stéréo I/Q `uint8`, `int16`, `int32` ou `float32` ;
- sélection du fichier par l'explorateur Windows depuis la liste des sources, démarrage automatique de la lecture, boucle optionnelle et retour au SDR sans relancer l'application ;
- démarrage de l'interface en mode découverte même lorsqu'aucun SDR n'est encore connecté ;
- identification visible de la source fichier, lecture temps réel, boucle optionnelle et fréquence centrale extraite du bloc HDSDR `auxi`, du nom ou explicitement configurée ;
- débit de sortie indépendant par destination UDP, sans suréchantillonnage, avec pipeline de rééchantillonnage mutualisé entre destinations équivalentes ;
- ajout et modification dans l'interface du débit, de la taille des datagrammes et de la profondeur de file de chaque destination ;
- datagrammes loopback de 8192 octets par défaut, maintien de 1200 octets sur le LAN et paramètres QMAP fixes à 96 kS/s / 1416 octets ;
- chemin direct sans conversion `CS16 -> complex64 -> CS16` pour les sorties au débit source et suppression de l'attente active du pacing SDR++ ;
- blocs de traitement Soapy, natifs et fichier portés à 16384 échantillons par défaut pour conserver 2 MS/s avec les trois sorties de référence ;
- 60 tests applicatifs, dont le démarrage sans SDR, la permutation SDR/fichier et trois sorties simultanées à 2 MS/s, 192 kS/s et 1 MS/s.

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
