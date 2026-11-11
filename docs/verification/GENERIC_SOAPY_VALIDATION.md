# Qualification des récepteurs Soapy génériques

Cette procédure qualifie la branche de développement postérieure à SDRbridge
0.6.1. Elle ne transforme pas la simple présence d'une factory Soapy en preuve
de fonctionnement matériel : chaque ligne doit être testée avec le récepteur
réel et son pilote Windows.

## Matrice confiée à Denis

| Matériel | Factory attendue | Premier débit conseillé | État |
|---|---|---:|---|
| Airspy R2 | `airspy` | 2,5 MS/s | à qualifier |
| Airspy HF+ | `airspyhf` | 768 kS/s | à qualifier |
| RTL-SDR avec E4000 | `rtlsdr` | 2,048 MS/s | à qualifier |
| RTL-SDR avec R820T | `rtlsdr` | 2,048 MS/s | à qualifier |
| LimeSDR Mini | `lime` | 2 MS/s, puis 10 MS/s | à qualifier |
| ADALM-Pluto original | `plutosdr` | 2 MS/s | à qualifier |
| Ettus USRP B100 | `uhd` | 1 MS/s, puis 4 MS/s | à qualifier immédiatement |

Le FunCube Dongle est volontairement hors périmètre : aucun adaptateur propre à
SDRbridge ne sera ajouté tant qu'il n'est pas présenté comme récepteur IQ par
un module Soapy natif et maintenu.

## Préparation du PC de validation

1. Avec l'installateur de validation 0.7.0.dev2, installer uniquement les
   pilotes Windows recommandés par le fabricant. PothosSDR n'est pas requis
   pour exécuter le paquet installé ; il ne sert qu'à reconstruire les modules
   depuis les sources.
2. Pour les clés RTL-SDR, vérifier que l'interface IQ utilise le pilote WinUSB
   approprié. Ne pas remplacer le pilote d'un autre périphérique par erreur.
3. Fermer les autres logiciels qui pourraient avoir ouvert le SDR.
4. Installer le paquet de validation SDRbridge fourni pour cette campagne.
5. Ne copier aucune DLL Soapy de SDRbridge dans PothosSDR, SDR++, ANTRACK ou un
   autre logiciel. Les piles restent isolées.

### Préparation particulière de l'USRP B100 sous Windows

Le B100 est un périphérique USB 2.0 hérité pris en charge par UHD. Avant de
lancer SDRbridge, vérifier que le pilote WinUSB UHD est installé dans le
Gestionnaire de périphériques et que les images compatibles avec la version
UHD 4.0 du runtime Pothos sont présentes. UHD charge automatiquement les images
du B100 au démarrage ; au besoin, utiliser le téléchargeur fourni par cette
même installation UHD et définir
`UHD_IMAGES_DIR` vers son répertoire `images`. Ne jamais mélanger des images
prises dans une autre version UHD.

La méthode recommandée sur le PC du B100 consiste à copier puis exécuter
`SDRbridge_Setup_0.7.0.dev2.exe`. Pour reconstruire et lancer la branche depuis
les sources à la place :

```powershell
git clone --branch codex/generic-soapy-uhd https://github.com/stephanerey/SDRbridge.git
cd SDRbridge
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\packaging\build_soapy_runtime.ps1
.\.venv\Scripts\python.exe .\launch_sdrbridge.pyw
```

Le script de runtime ne requiert pas le SDK SDRplay sur un PC de test générique.
Il requiert en revanche PothosSDR x64 et Visual Studio Build Tools/CMake pour
compiler les adaptateurs privés ABI 0.8. La présence de `uhd` dans la ligne
`Available factories` prouve uniquement le chargement logiciel ; le B100 doit
ensuite apparaître dans la liste **Source** et réussir l'essai RX ci-dessous.

Dans SDRbridge 0.7.0.dev2, le B100 est limité aux débits CS16 utilisables jusqu'à
8 MS/s. La longue liste de bandes passantes UHD du frontend est masquée car elle
ne représente pas la largeur IQ. Le contrôle `ADC-pga` reste exposé et doit être
testé en observant son effet sur le niveau reçu.

## Essai à exécuter pour chaque matériel

1. Ouvrir SDRbridge sans lancer l'acquisition, puis actualiser les sources.
2. Vérifier que le nom du matériel apparaît et noter le libellé complet.
3. Sélectionner le matériel. Vérifier que fréquence d'échantillonnage, bande
   passante, antenne, AGC et gains n'apparaissent que s'ils sont réellement
   exposés par son module Soapy.
4. Choisir le premier débit de la matrice, lancer l'acquisition et attendre que
   le bouton passe à l'état actif.
5. Pendant au moins 60 secondes, vérifier un spectre ou waterfall vivant, un
   débit mesuré cohérent et **Total losses = 0**.
6. Ajouter un client UDP local au même débit, puis vérifier encore 60 secondes
   que le flux client reste stable et que les pertes restent nulles.
7. Changer la fréquence dans SDRbridge et vérifier le déplacement attendu du
   spectre. Tester chaque gain/AGC visible ; un contrôle absent n'est pas un
   défaut si le module ne l'expose pas.
8. Effectuer cinq cycles Stop/Play, puis un changement vers Simulation et un
   retour au SDR. Aucun cycle ne doit rester sur « waiting for new blocks ».
9. Pour LimeSDR Mini seulement, refaire l'essai à 10 MS/s avec une sortie UDP à
   2 MS/s, puis à 4 MS/s si la machine le permet.
10. Exporter le rapport ZIP de diagnostics et prendre une capture des onglets
    Radio et Clients_Streams.

## Éléments à retourner

Pour chaque appareil : modèle/tuner, version du pilote, libellé SDRbridge,
débits disponibles, contrôles visibles, résultat Stop/Play, pertes finales,
rapport de diagnostics et captures. Toute réception réelle doit rester marquée
« non qualifiée » dans la documentation tant que ces preuves ne sont pas
archivées.
