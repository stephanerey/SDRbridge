# Source SDR++ pour SDRbridge SDBU v2

Ce dépôt construit une source native SDR++ qui reçoit les datagrammes UDP **SDBU v2** de SDRbridge. La DLL valide l'en-tête réseau de 72 octets, accepte les IQ `CS16` et `CF32`, convertit les échantillons vers le flux complexe interne de SDR++, applique automatiquement le taux d'échantillonnage et la fréquence centrale annoncés, puis expose les compteurs d'erreurs, trous et paquets anciens.

La DLL x64 précompilée est versionnée dans [`bin/sdbu_source.dll`](bin/sdbu_source.dll). Les scripts reconstruisent cette même copie dans `bin/`.

La cible locale vérifiée est SDR++ 1.3.0 :

```text
E:\Radio\sdrpp_windows_x64_1.3.0\sdrpp_windows_x64
```

Le cœur installé a été compilé le 25 mars 2026. La compilation utilise les en-têtes officiels SDR++ de la révision `a6df4d58e5f6b3045883a70aeb8fb41fd5dbf1d9`, immédiatement antérieure au binaire, et génère une bibliothèque d'import depuis le `sdrpp_core.dll` réellement installé.

## Construire et installer

```powershell
.\scripts\build.ps1
.\scripts\install.ps1
```

L'installation copie `sdbu_source.dll` dans `modules`, ajoute une instance `SDRbridge SDBU v2` à `config.json` et conserve une sauvegarde ainsi qu'un manifeste de retour arrière. Elle refuse de modifier le dossier si cette version de SDR++ est active.

Pour annuler l'installation :

```powershell
.\scripts\uninstall.ps1
```

## Utilisation

Dans SDR++, sélectionner la source **SDRbridge SDBU v2**, conserver l'écoute sur `127.0.0.1:7355`, puis démarrer la source. Côté SDRbridge, choisir la destination UDP `127.0.0.1:7355` avec le transport `sdbu_v2`.

La syntonisation reste volontairement en lecture seule côté DLL : la fréquence centrale vient de l'en-tête SDBU et met à jour le sélecteur supérieur, le VFO et l'échelle du waterfall. Un changement de fréquence dans SDR++ est ramené à la valeur effective du bridge et ne pilote pas le RSPdx. SDRbridge conserve l'autorité RF.

## Limites

- IPv4 unicast uniquement dans cette première version.
- Pas de retransmission ni de correction des pertes UDP ; les trous restent visibles dans les compteurs.
- Le chargement réel dans SDR++ et la réception d'un flux doivent être requalifiés après toute mise à jour du cœur SDR++.

Licence : GPL-3.0-or-later, cohérente avec SDR++.
