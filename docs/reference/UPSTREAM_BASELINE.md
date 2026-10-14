# Référence amont vérifiée

Date de lecture : 13 octobre 2026. Dépôt : [f5jwf/SDR_Bridge](https://github.com/f5jwf/SDR_Bridge/tree/7efd536e059e60130884e6aef3a23e1e5aea79dc). Commit : `7efd536e059e60130884e6aef3a23e1e5aea79dc`.

La lecture initiale a été suivie d'un import contrôlé de43 fichiers (README local conservé), d'un audit ciblé et de quatre tests amont réussis. Voir [PREPARATION_REPORT](PREPARATION_REPORT.md). Aucun essai matériel ni audit exhaustif n'est revendiqué.

| Fichier observé | Fait vérifié | Conséquence pour la transition |
|---|---|---|
| `model.py` | IQBlock : sequence, timestamp_ns, config_revision, sample_count, payload ; seul format enum `s16le_iq` | Les nouveaux champs ne sont pas déjà présents ; adaptation explicite |
| `control.py` | JSON UTF-8 par ligne ; status/register/heartbeat/set_config ; écoute loopback 47631 ; set_config exige un token local | Conserver le chemin des clients existants ; ne pas l'exposer directement au LAN |
| `ring.py` | Magic SDBR, version 1 ; en-tête `<4sIIIIQ` ; slot `<QQIIQ` ; payload CS16 intercalé | Contrat partagé potentiellement consommé en C++ ; pas de changement silencieux |
| `ring.py` | Publication par committed_seq, lecteur lent rattrapé ; option de lecture sans copie | Vérifier cohérence pendant réécriture et durée de vie des vues ; ne pas supposer une sûreté interprocessus prouvée |
| `udp.py` | Magic SDBU, version 1 ; header `<4sBBHQQIII` ; destination unique | Le nouveau protocole v2 décrit ailleurs n'est pas compatible par défaut |
| `config.example.json` | `max_clients: 4`, source simulée, UDP désactivé | Limite à supprimer dans un lot ciblé après localisation des usages |
| `pyproject.toml` | Version 0.2.0, Python ≥3.11, numpy ≥2.0 | Pas de dépendances Qt/Soapy/FIR supposées installées |

Chemins relatifs des fichiers Python : `src/sdr_bridge/`. Les tests amont recensés sont `tests/test_core.py` et `tests/test_udp.py`. Les parties natives incluent ExtIO et le bridge SDRplay ; leurs sources devront être lues avant mutation du ring ou du contrôle.

Le ring SDBR v1 et l'UDP SDBU v1 ont des versions indépendantes. Préserver une interface ne garantit pas la préservation de l'autre. Un nouveau champ Python n'est pas une mise à jour automatique du format partagé.

La révision importée est celle indiquée ici. Les futurs changements de provenance doivent être explicites ; enregistrer les erreurs préexistantes séparément des régressions. Vérifier les licences avant redistribution, qui n'est pas autorisée par la préparation.
