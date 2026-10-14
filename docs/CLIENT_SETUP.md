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

Dans SDR++, ajouter la source **Network** et choisir l’entrée UDP locale sur le port `7355`, le taux `192000 S/s`, le format IQ signé 16 bits little-endian et la fréquence centrale effective affichée par SDRbridge. Le profil `sdrpp_raw_cs16` est le seul flux SDR++ volontairement sans en-tête ; `sdbu_v2` est le protocole natif SDRbridge et n’est pas directement sélectionnable dans SDR++.

Le client natif de diagnostic est `release-v0.3\SDR_Bridge_Native_Client\SDR_Bridge_Native_Client.exe` ou `sdr-bridge-native-client` depuis l’environnement Python. Le protocole SDBU v2 émet un en-tête de 72 octets et reste distinct du flux raw SDR++.

Les connecteurs livrés sont sous `release-v0.3\Connectors\HDSDR` et `Connectors\ANTRACK`. Leur copie dans une installation HDSDR ou ANTRACK est une étape manuelle de recette, non exécutée par le build.

HDSDR 2.81a, ANTRACK 2.1.0 et SDR++ 1.2.1 doivent être testés sur les installations réellement présentes. Les tests locaux vérifient l’ExtIO Win32, le shim ANTRACK et le format raw ; ils ne constituent pas une qualification de ces logiciels tiers.

QMAP/Linrad TIMF2 reste différé. WSJT-X doit passer par une chaîne audio aval, pas par un flux IQ direct.
