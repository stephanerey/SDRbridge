# Validation — captures SDR++ et HDSDR

Date : 6 novembre 2026

## Contrats produits

- SDR++ : RIFF/WAVE, deux canaux I/Q, PCM signé 16 bits, fréquence exacte en `Hz` dans le nom.
- HDSDR : même payload PCM int16, plus un chunk `auxi` de 164 octets avec deux `SYSTEMTIME`, fréquence centrale, taux et bande passante.
- SigMF 1.2.6 : comportement existant conservé.

Les profils CF32 sont convertis vers PCM int16 par le thread recorder, sans travail supplémentaire dans le callback source. Les fichiers existants sont refusés et une discontinuité clôt la capture.

## Preuves

- `python -m unittest discover -s tests` : 63 tests réussis.
- Les tests binaires relisent les deux WAV avec `inspect_iq_wav`, vérifient taux, fréquence, nombre d'échantillons, payload et présence/absence du chunk `auxi`.
- L'instance graphique isolée `capture-qa` a affiché les trois formats et ouvert la boîte Windows **Save IQ capture** directement dans `C:\Projets\SDRBridge\Captures`.
- Une capture SDR++ réelle de l'instance simulée a été finalisée : 44 105 728 octets IQ, 11 026 432 échantillons, 2 000 000 S/s, centre 144 300 000 Hz.

## Limites

Le WAV produit est le RIFF classique actuellement utilisé par le recorder SDR++ officiel; RF64 y est désactivé. La limite est donc 4 Gio. La relecture directe par les applications tierces SDR++ et HDSDR reste une qualification externe distincte.
