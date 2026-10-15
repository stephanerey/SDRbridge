# Historique des versions

## 0.4.0 — en préparation

- catalogue SoapySDR filtré avec modèle et numéro de série dans la liste des sources ;
- couche ctypes Soapy intégrée au paquet, avec PothosSDR comme runtime externe ;
- instances nommées avec configuration, ports et journaux isolés ;
- sélection matérielle explicite par `--device-id` et décalage de ports par `--port-offset` ;
- inventaire reproductible des récepteurs par `--source soapy --list-devices` ;
- journaux persistants rotatifs et diagnostic des arrêts/crashs ;
- smoke RX matériel reproductible, séparé puis simultané ;
- validation du RSPdx natif et du clone RSP1 Soapy en deux processus simultanés ;
- version de l’application et du packaging portée à 0.4.0.

## 0.3.0 — publiée

- cœur RX mono-source, SDBR v2 et SDBU v2 ;
- connecteurs SDR++ et HDSDR ;
- backend SDRplay natif, GUI Qt, profils DSP, capture/replay SigMF et packaging Windows.
