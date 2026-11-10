# Aide SDRbridge 0.6

SDRbridge reçoit un flux IQ depuis un récepteur SDR ou un fichier, puis le
distribue simultanément à plusieurs logiciels et enregistrements. Chaque client
UDP peut avoir son propre débit d'échantillonnage.

## Démarrage rapide

1. Pour un récepteur SDRplay, installez d'abord l'API et le pilote SDRplay 3.15
   depuis le site officiel, puis redémarrez Windows si l'installeur le demande.
2. Lancez SDRbridge. Python, Qt et SoapySDR sont déjà inclus dans SDRbridge.
3. Dans **Radio**, sélectionnez le SDR et choisissez le débit IQ. Laissez la
   bande passante sur **Auto**.
4. Appuyez sur **Acquisition**. Le bouton est orange pendant l'ouverture du
   matériel, vert lorsque le flux est réellement actif et gris à l'arrêt.
5. Dans **Clients & Streams**, ajoutez les destinations nécessaires.

## Configurations usuelles

| Client | Destination typique | Transport | Débit |
|---|---|---|---:|
| SDR++ | `127.0.0.1:7355` | SDR++ raw CS16 ou SDBU v2 | selon le client |
| QMAP 0.6 | `127.0.0.1:50004` | QMAP/Linrad | 96 kS/s fixe |
| Second SDR++ | `127.0.0.1:7357` | SDR++ raw CS16 ou SDBU v2 | par exemple 192 kS/s |

Des débits identiques partagent un traitement DSP. Une destination à débit plus
faible reçoit un flux réellement décimé et filtré, pas seulement moins de
paquets.

## Fichiers IQ

Dans la liste des sources, choisissez **Fichier IQ…**. SDRbridge lit les WAV ou
RF64 I/Q stéréo produits par HDSDR et SDR++, ainsi que les captures SigMF. Les
paramètres issus du fichier sont affichés mais ne sont pas modifiables. Activez
**Boucler le fichier** pour recommencer à la fin.

L'onglet **Captures** enregistre en SigMF 1.2.6, SDR++ WAV int16 stéréo ou HDSDR
WAV int16 stéréo. Le dossier proposé par défaut est `Captures` dans le dossier
SDRbridge.

## Réglages RF

- **Débit d'échantillonnage** : largeur du flux IQ produit par le SDR.
- **Bande passante** : filtre analogique/IF réellement exposé par le matériel.
  Le mode Auto choisit la valeur disponible la plus proche du débit demandé.
- **IFGR/RFGR** : réductions de gain du SDRplay. Un déplacement vers la droite
  correspond visuellement à davantage de gain, même si le matériel expose une
  atténuation.
- **Profils RF** : appliquent automatiquement antenne, gains, AGC et bande
  passante selon la fréquence.

## Pertes et performances

**Total losses** compte les pertes source, DSP et UDP. Une valeur qui augmente
indique qu'un échantillon ou un bloc utile n'a pas pu être traité. La valeur
**SDRbridge CPU** est exprimée en cœurs logiques utilisés, pas en pourcentage de
la machine entière.

Si des pertes apparaissent :

1. réduisez les FFT très grandes et utilisez Waterfall seul ;
2. réduisez le débit d'un client ou supprimez un client inutilisé ;
3. augmentez modérément la file du client ;
4. utilisez **Diagnostics → Exporter le rapport ZIP** et joignez le fichier au
   rapport de bug.

## HDSDR et clients ExtIO locaux

HDSDR n’utilise pas les destinations UDP `7355`, `7356`, etc. L’ExtIO se
connecte au contrôle local `127.0.0.1:47631`, puis lit le ring SDBR v2 en
mémoire partagée. Il n’y a donc aucun port IQ à configurer dans HDSDR.

L’ExtIO lit le débit complet du ring maître, sans décimation par client. Une
source à 10 MS/s est remise à HDSDR à 10 MS/s. Chaque HDSDR apparaît dans
**Consommateurs actifs** et dans le **Débit IQ logique**, mais pas dans le
**Débit UDP utile** ni le débit réseau. Plusieurs instances partagent le même
ring écrit une seule fois ; chacune conserve néanmoins son propre coût CPU de
copie, FFT, waterfall et démodulation.

HDSDR 2.81a et SDRuno 1.42.1710 sont les hôtes ExtIO certifiés. Pour SDRuno,
copiez la DLL dans `C:\Program Files (x86)\SDRplay\SDRuno`, puis lancez
`SDRuno.EXTIO.exe` et non `SDRuno.exe`. **In SR** doit afficher le débit source.
Les autres hôtes ExtIO Win32 ne sont pas garantis sans essai.

## Prérequis

- Windows 10 ou Windows 11 x64 ;
- SDRplay : API/pilote officiel 3.15 ;
- SDR++ : installation x64 plus le module fourni avec SDRbridge ;
- HDSDR : installation 32 bits plus l'ExtIO fourni ;
- QMAP et ANTRACK : installations séparées, sans pile Soapy partagée avec
  SDRbridge.

SDRbridge inclut son propre SoapySDR. Il ne faut pas copier ses DLL dans
PothosSDR, ANTRACK ou SDR++.

Le paquet 0.6.1 inclut uniquement le module matériel `SoapySDRPlay3`. Les
SDRplay sont donc les seuls récepteurs matériels utilisables immédiatement avec
l'installateur. Un RTL-SDR, USRP/UHD, Airspy, HackRF ou LimeSDR nécessite un
module Soapy compatible ajouté et qualifié dans le runtime privé de SDRbridge ;
les modules de l'installation PothosSDR globale ne sont pas chargés.

## Destinations UDP sur le LAN

Les destinations UDP distantes sont désactivées par défaut. Dans
**Paramètres**, activer **Autoriser UDP LAN** avant d'ajouter une adresse hors
de la boucle locale. Cette autorisation est enregistrée immédiatement et
n'expose pas le contrôle RF sur le réseau. Pour le LAN, utiliser des datagrammes
de 1200 octets ; l'éditeur remplace automatiquement la valeur loopback de 8192
octets lors de la saisie d'une adresse distante. Le récepteur doit écouter sur
son adresse LAN ou `0.0.0.0`, et son pare-feu doit autoriser le port UDP choisi.

## Support, licence et dons

SDRbridge est distribué sous GNU GPL v3 ou ultérieure, sans garantie. Les
auteurs sont Stéphane REY F1TJJ et Philippe Borghini F5JWF. Le code source et
les rapports de problème sont disponibles sur
https://github.com/stephanerey/SDRbridge.

Le logiciel a été développé avec l'assistance de l'IA, sous direction humaine,
avec revue, essais matériels et validation des versions, en utilisant la SR
Method 4.1 d'Auroramind :
https://github.com/syl2042/Aurora_SR_method_codex_pack.
