# Validation — source fichier et sorties multi-débits

Date : 6 novembre 2026

## Corpus HDSDR réel

Les trois fichiers HDSDR fournis localement pour la validation ont été ouverts en lecture seule ; ils ne sont pas inclus dans le dépôt.

| Fichier | Encodage | Taux | Fréquence `auxi` | Échantillons IQ | Durée |
|---|---:|---:|---:|---:|---:|
| `HDSDR_20261101_084559Z_144091kHz_RF.wav` | int16 stéréo | 2 000 000 S/s | 144 091 210 Hz | 362 332 160 | 181,166 s |
| `HDSDR_20261101_085759Z_144091kHz_RF.wav` | int16 stéréo | 2 000 000 S/s | 144 091 210 Hz | 600 000 000 | 300,000 s |
| `HDSDR_20261101_090259Z_144091kHz_RF.wav` | int16 stéréo | 2 000 000 S/s | 144 091 210 Hz | 413 791 232 | 206,896 s |

Le bloc `auxi` HDSDR commence après le `fmt ` et fournit la fréquence précise. Le nom de fichier n'en donne qu'une valeur arrondie à 144 091 kHz. Les trois fichiers ont produit un datagramme SDBU v2 de 8192 octets à 2 MS/s, avec la fréquence exacte 144 091 210 Hz.

Sur le fichier de 300 secondes, les trois sorties simultanées ont été reçues à 2 000 000, 192 000 et 1 000 000 S/s. Les trois en-têtes annonçaient 144 091 210 Hz. Après trois secondes : débit source mesuré 1,990 MS/s, aucune perte de file source et aucune erreur source.

## Charge simulée reproductible

Configuration : source simulée 2 MS/s, blocs de 16 384 échantillons, sortie SDR++ raw à 2 MS/s et sorties SDBU à 192 kS/s et 1 MS/s, récepteurs loopback drainés pendant cinq secondes.

- débit source mesuré : 1,993 MS/s ;
- charge processus : 0,991 cœur CPU équivalent ;
- traitement dispatcher moyen : 6,408 ms pour un budget de 8,192 ms ;
- pertes source : 0 ;
- erreurs source : 0 ;
- pertes dans les trois files UDP : 0 ;
- datagrammes émis : 4 880 / 613 / 3 060.

Cette mesure courte n'est pas une recette d'endurance. Elle valide que la configuration de référence tient la cadence nominale sur la machine de développement.

## Charge réelle avec trois clients

Mesure de 15 secondes sur l'Intel Core i5-9500 (6 cœurs), avec le RSP1A à 2 MS/s, SDR++ à 2 MS/s, un second SDR++ à 192 kS/s et QMAP à 96 kS/s :

- SDRbridge : 11,4 % du processeur total en moyenne, 15,0 % au maximum ;
- deux SDR++ : 4,1 % au total en moyenne ;
- QMAP : 0,6 % en moyenne sur la fenêtre ;
- aucune perte de file ni erreur sur les trois destinations UDP ;
- charge machine moyenne : 47,1 %, dont une part importante provenait de ChatGPT/Codex et des autres applications ouvertes, pas de la chaîne SDR.

Une seconde fenêtre de huit secondes a confirmé SDRbridge à 10,9 %, les deux SDR++ à 4,7 % et QMAP à 2,0 %. Le transport SDR complet utilise donc environ 16 à 18 % du processeur total dans cette configuration ; la machine conserve une marge utile malgré des pointes globales provoquées par les autres applications.

## Capture réelle

Une capture depuis l'onglet **Captures**, profil Master CS16, a été démarrée et arrêtée avec les trois clients actifs. Le recorder a finalisé 9 631 440 échantillons (`ci16_le`) à 2 MS/s et 1 297 600 000 Hz ; la paire SigMF 1.2.6 a été validée par `validate_sigmf`.

Le recorder produit actuellement `.sigmf-data` + `.sigmf-meta`. Il ne produit pas encore un WAV/RF64 HDSDR/SDR++ ; la lecture de ces fichiers et l'enregistrement SigMF sont volontairement séparés.

## Interface

Le rendu Windows de l'onglet **Outputs & Clients** se trouve dans `ui-windows/outputs.png`. Les trois débits effectifs, les tailles de datagramme et les profondeurs de file y sont visibles et éditables. Les tests Qt vérifient l'ouverture de l'explorateur depuis la liste des sources, le verrouillage QMAP à 96 kS/s / 1416 octets et l'indication explicite **Fichier IQ …**.

`ui-windows/file-source.png` montre l'un des fichiers HDSDR réels chargé depuis l'interface : fréquence `auxi` 144 091 210 Hz, source `file/wav`, case de boucle active et spectre alimenté.

## Suite de tests

`python -m unittest discover -s tests -v` : 60 tests sur 60 réussis.
