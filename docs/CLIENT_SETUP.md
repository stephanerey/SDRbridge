# Connexion des clients à SDRbridge 0.3

Le lancement par défaut est simulé et n’ouvre aucun matériel. Depuis `E:\PLDesign\SDRbridge` :

```powershell
.\.venv\Scripts\python.exe -m sdr_bridge --source simulated --headless --auto-start
```

Pour l’interface Qt, omettre `--headless`. Le contrôle natif loopback est désactivé par défaut ; l’activer explicitement avec `--enable-network` et, si nécessaire, `--native-control-port 47632`. Aucun pare-feu LAN n’est modifié.

La commande ci-dessus utilise volontairement la source simulée : l’interface affiche alors « SIMULATION — aucun SDR physique connecté ». Pour tester SDR++ Network Source en local avec des IQ CS16 bruts (sans en-tête), lancer :

```powershell
.\.venv\Scripts\python.exe -m sdr_bridge --source simulated --auto-start --udp 127.0.0.1:7355 --udp-transport sdrpp_raw_cs16
```

Dans SDR++, ajouter la source **Network** et choisir l’entrée UDP locale sur le port `7355`, le taux affiché comme **Sampling** dans SDRbridge (par défaut `2000000 S/s`), le format IQ signé 16 bits little-endian (`Int16`) et la fréquence centrale effective affichée par SDRbridge. Le backend RSPdx natif expose les modes `2`, `6`, `8` et `10 MS/s`; après un changement de Sampling, reporter exactement le nouveau taux dans SDR++. Le transport opérateur `sdrpp_raw_cs16` est volontairement sans en-tête : la fréquence centrale et le taux ne sont donc pas transmis à SDR++ et doivent être renseignés manuellement.

Une source native **SDRbridge SDBU v2** est aussi installée pour SDR++ 1.3.0 sous `E:\Radio\sdrpp_windows_x64_1.3.0\sdrpp_windows_x64`. Elle écoute par défaut `127.0.0.1:7355`, valide l'en-tête SDBU v2 de 72 octets, accepte CS16/CF32 et applique au DSP de SDR++ le taux et la fréquence centrale annoncés. Pour ce chemin, utiliser `--udp-transport sdbu_v2`; `config.native-sdrpp.json` est préparé ainsi pour le prochain démarrage. La source reste en lecture seule : une syntonisation dans SDR++ ne pilote jamais le RSPdx. Le module, la DLL x64 précompilée, ses scripts de build/retour arrière et ses preuves sont versionnés dans `clients/sdrpp_sdbu_source`.

Le champ **Bandwidth** est indépendant du Sampling : il sélectionne le filtre RF SDRplay. SDRbridge ne propose que les largeurs compatibles avec le Sampling courant (par exemple, à `2 MS/s`, les filtres 5–8 MHz sont masqués). Changer Bandwidth filtre le spectre sans changer le débit IQ ; changer Sampling reconfigure le flux maître.

Plusieurs clients UDP peuvent être servis simultanément. Depuis l’onglet **Outputs & Clients**, ajouter par exemple `127.0.0.1:7356` avec le transport **SDR++ raw CS16** ; conserver la première destination sur `7355`, puis configurer chaque instance SDR++ sur son port respectif. En ligne de commande, répéter `--udp` :

```powershell
.\release-v0.3\SDR_Bridge\SDR_Bridge.exe --config .\config.native-sdrpp.json `
  --udp 127.0.0.1:7355 --udp 127.0.0.1:7356 `
  --udp-transport sdrpp_raw_cs16
```

Un client SDR++ raw ne réalise pas de handshake ; il figure donc comme destination UDP avec ses statistiques, pas comme session native confirmée.

Important : la destination `--udp ... --udp-transport sdrpp_raw_cs16` lit actuellement le ring maître SDRbridge et transmet le taux source effectif, sans la décimation des profils internes `192 kS/s`. Régler SDR++ sur `192000 S/s` comprime l’axe fréquentiel d’un facteur `2000000/192000 = 10,4167` et transforme une émission FM de 150–200 kHz en une trace d’environ 14–19 kHz. Si le taux effectif du périphérique est changé dans SDRbridge, reporter exactement cette nouvelle valeur dans SDR++.

Pour une destination loopback (`127.0.0.1`), SDRbridge regroupe automatiquement le raw CS16 en datagrammes de 8 Ko afin de limiter la charge UDP à 2 MS/s. Les destinations réseau utilisent le budget conservateur de 1 200 octets pour éviter la fragmentation IP.

Le client natif de diagnostic est `release-v0.3\SDR_Bridge_Native_Client\SDR_Bridge_Native_Client.exe` ou `sdr-bridge-native-client` depuis l’environnement Python. Le protocole SDBU v2 émet un en-tête de 72 octets et reste distinct du flux raw SDR++.

Les connecteurs livrés sont sous `release-v0.3\Connectors\HDSDR` et `Connectors\ANTRACK`. Leur copie dans une installation HDSDR ou ANTRACK est une étape manuelle de recette, non exécutée par le build.

HDSDR 2.81a, ANTRACK 2.1.0 et SDR++ 1.2.1 doivent être testés sur les installations réellement présentes. Les tests locaux vérifient l’ExtIO Win32, le shim ANTRACK et le format raw ; ils ne constituent pas une qualification de ces logiciels tiers.

QMAP/Linrad TIMF2 reste différé. WSJT-X doit passer par une chaîne audio aval, pas par un flux IQ direct.
