[English documentation](HARDWARE_COMPATIBILITY.md)

# Matrice de validation matérielle

SDRbridge est piloté par les capacités : il n'identifie pas un modèle de
récepteur pour inventer des contrôles ou des limites de débit. Le tableau
ci-dessous consigne les configurations réellement essayées. Il constitue une
preuve de test et non une liste de compatibilité codée en dur.

L'utilisateur doit d'abord installer les pilotes, API, firmwares et images
matérielles du constructeur. Le récepteur doit fonctionner correctement par
l'intermédiaire de son module SoapySDR avant que SDRbridge puisse l'utiliser.

« Débit IQ maximal testé » désigne le débit source le plus élevé essayé pendant
la validation enregistrée. Ce n'est pas nécessairement la limite absolue du
matériel et cette valeur est distincte de la bande passante analogique du
frontend RF.

| Récepteur | Backend Soapy | Débit IQ maximal testé | Résolution source / transport | État de validation |
|---|---|---:|---|---|
| SDRplay RSP1A | `sdrplay` | 10 MS/s | échantillons hôte CS16 | RX, contrôles dynamiques et sorties simultanées 4 MS/s plus QMAP validés sous Windows 11 |
| SDRplay RSPdx | SDRplay natif et `sdrplay` | 2 MS/s | échantillons hôte CS16 | RX et contrôles matériels validés sous Windows |
| MSI Panadapter compatible RSP1 | `sdrplay` | Non consigné | échantillons hôte CS16 | RX validé seul et simultanément avec un RSPdx |
| Ettus USRP B100 | `uhd` | 16 MS/s | SC8 sur le lien matériel, transfert hôte CS8, flux bridge CS16 | détection, RX, débit et sélection du transport validés sous Windows 11 |
| Airspy R2 | `airspy` | À faire | À faire | validation sur matériel réel confiée |
| Airspy HF+ | `airspyhf` | À faire | À faire | validation sur matériel réel confiée |
| RTL-SDR E4000 | `rtlsdr` | À faire | À faire | validation sur matériel réel confiée |
| RTL-SDR R820T | `rtlsdr` | À faire | À faire | validation sur matériel réel confiée |
| LimeSDR Mini | `lime` | À faire | À faire | validation sur matériel réel confiée |
| ADALM-Pluto | `plutosdr` | À faire | À faire | validation sur matériel réel confiée |

Pour un nouveau résultat, consigner le récepteur exact, les versions de Windows
et du pilote, le backend Soapy, le débit source maximal testé, le transport et
la résolution IQ effectifs, les sorties clientes, la durée du test et le
rapport de diagnostic. Ne pas déclarer un récepteur validé au seul motif que sa
factory Soapy se charge.

Utiliser la [procédure de qualification Soapy générique](verification/GENERIC_SOAPY_VALIDATION_FR.md)
pour obtenir des essais reproductibles.
