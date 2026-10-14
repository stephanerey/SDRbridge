# S4 — Réseau et protocole natif proposé

Statut : contrat proposé v0.2, à valider pour le lot réseau. Il décrit le nouveau protocole natif ; il n'affirme aucune compatibilité automatique SDR++, QMAP ou ExtIO. Couverture : REQ-016 à REQ-023, REQ-019 et REQ-014.

## 1. Séparation et compatibilité

Conserver le contrôle historique loopback 47631 et son adaptateur tant que les clients locaux en dépendent. Le nouveau contrôle natif utilise un port distinct proposé, 47632, configurable et désactivé par défaut. L'UDP historique SDBU v1 reste identifié comme tel ; aucune bascule silencieuse vers le format v2 ci-dessous.

Les fonctions de l'ancienne API sont encapsulées si besoin ; ne pas ouvrir au LAN le `set_config` historique protégé par un token local. L'administration RF distante est hors périmètre.

## 2. Contrôle natif TCP/JSON v1

Transport : un objet JSON UTF-8 par ligne LF, maximum 65 536 octets LF compris. Une connexion traite les requêtes en ordre et répond une fois par requête ; aucun événement asynchrone intercalé dans cette première version. Les clients interrogent les états et renouvellent leur présence. JSON mal formé : réponse d'erreur si une réponse bornée est possible puis fermeture ; ligne trop longue : fermeture immédiate avec log borné.

Enveloppe : `api_version: 1`, `request_id` chaîne non vide ≤64 caractères, `method` et `params` objet. Réponse : même `request_id`, `ok`, puis `result` ou `error: {code, message}`. Si l'identifiant ne peut être décodé, il est null dans l'erreur. Entiers 64 bits sémantiques transportés en chaînes décimales dans JSON pour éviter la perte de précision des clients.

| Méthode | Paramètres minimaux | Résultat / conditions |
|---|---|---|
| hello | client_name ≤128 caractères, client_version ≤64, token si politique activée | run_id UUID, client_id, rôle read, heartbeat_interval_s=5, lease_timeout_s=15 ; doit être la première requête |
| list_sources | aucun | Identités, état, époque, configuration effective et capacités de sortie |
| list_profiles | aucun | Profils publiés et immuables, formats/protocoles disponibles |
| subscribe | source_id, profile_id, profile_revision, transport, port UDP si unicast | subscription_id, wire_stream_id, epoch, endpoint et paramètres effectifs ; pas de réglage RF |
| unsubscribe | subscription_id | Fermeture du seul abonnement appartenant à cette session ; répétition renvoie déjà fermé sans erreur destructive |
| heartbeat | telemetry facultative bornée | Renouvelle le bail et retourne état minimal ; télémétrie déclarative non fiable à distinguer des mesures serveur |
| get_status | aucun | État serveur et abonnements de la session |
| goodbye | aucun | Libère les abonnements de la session puis ferme |

Une méthode inconnue ou un champ non autorisé dans les méthodes de mutation est refusé ; les champs d'une télémétrie optionnelle inconnue peuvent être ignorés si leur taille reste bornée. La V1 ne propose pas de `set_config`, création de profil opérateur ni arbitrage de contrôle sur ce canal.

Erreurs minimales : `BAD_REQUEST`, `UNSUPPORTED_VERSION`, `UNAUTHORIZED`, `NOT_REGISTERED`, `UNKNOWN_SOURCE`, `SOURCE_NOT_RUNNING`, `UNKNOWN_PROFILE`, `UNSUPPORTED_PROFILE`, `RESOURCE_LIMIT`, `DESTINATION_DENIED`, `INTERNAL_ERROR`. Le détail interne reste dans les logs serveur, pas dans la réponse distante.

Sur LAN/VPN, jeton de lecture obligatoire dans la proposition P-12 ; pas de jeton par défaut codé en dur. Sa valeur est référencée via un secret local, jamais exportée dans un preset. TCP/JSON n'apporte pas de chiffrement applicatif : limiter aux interfaces privées autorisées ou au VPN ; ne pas le présenter comme transport Internet sécurisé.

La socket unicast souscrite par un client vise son adresse pair TCP et le port demandé, pas une IP arbitraire fournie. Les destinations libres ne peuvent être créées que par l'opérateur local. Les requêtes sont bornées en débit (proposition : 20/s par session, tolérance de rafale 40) et les abonnements consomment des budgets configurés. Ces protections ne sont pas une limite produit fixe du nombre de clients.

La déconnexion TCP libère immédiatement ses abonnements ; sans nouvelle présence pendant 15 s, les libérer également. Les destinations opérateur ont leur propre cycle de vie et ne disparaissent pas quand un client natif se déconnecte.

## 3. Émission UDP

Unicast : files bornées par destination, erreurs comptées indépendamment. Multicast : groupe IPv4 et interface choisis par l'opérateur, TTL initial 1, loopback multicast désactivé sauf test explicite. Le nombre d'auditeurs multicast n'est pas déduit des émissions. IPv6 est une extension à décider, pas une promesse implicite.

Budget initial du datagramme applicatif : 1 200 octets, header compris ; il ne comprend pas les en-têtes IP/UDP. Il doit pouvoir être réduit pour un chemin VPN. Aucune trame native ne découpe un échantillon complexe. CS16 : au plus 282 complexes pour 72 octets de header. CF32 : au plus 141. Le dernier datagramme peut être plus court.

V2 transporte une suite d'échantillons par datagramme et ne demande pas de réassembler un grand bloc réseau. Pas de retransmission UDP. Le récepteur suit séquences/index ; un paquet ancien peut être ignoré avec compteur et un trou doit rester observable. Les applications nécessitant un jitter buffer le définissent côté récepteur, sans inventer de garantie serveur de livraison.

## 4. Header SDBU v2 — proposition précise

Tous les champs multioctets du header sont en big-endian. Payload CS16/CF32 little-endian selon S3. Longueur du header exactement 72 octets pour cette version. Le premier paquet de chaque époque porte DISCONTINUITY ; la description complète est également obtenue par le contrôle.

| Offset | Octets | Champ | Règle |
|---|---|---|---|
| 0 | 4 | magic | ASCII SDBU |
| 4 | 1 | version | 2 |
| 5 | 1 | format | 1=CS16 ; 2=CF32 |
| 6 | 2 | flags | bit0 TIME_VALID ; bit1 HARDWARE_ORIGIN ; bit2 DISCONTINUITY ; bit3 REPLAY ; autres zéro |
| 8 | 2 | header_bytes | 72 |
| 10 | 1 | time_domain | 0 unknown ; 1 device_relative ; 2 host_monotonic ; 3 unix_utc ; 4 replay_relative |
| 11 | 1 | reserved | 0 |
| 12 | 4 | wire_stream_id | Identité de sortie allouée dans run_id, non nulle ; pas réutilisée dans le run |
| 16 | 8 | epoch | Époque S2 de la source associée |
| 24 | 8 | packet_sequence | Commence à 0 par sortie/époque, progresse même si send échoue |
| 32 | 8 | first_sample_index | Index de sortie du premier complexe |
| 40 | 8 | timestamp_ns | Temps du premier complexe ; 0 si non valide |
| 48 | 4 | config_revision | Révision effective, non nulle |
| 52 | 4 | sample_rate_sps | Taux de sortie entier strictement positif |
| 56 | 8 | center_frequency_hz | Fréquence RF centrale, unsigned ; offset zéro en V1 produit |
| 64 | 4 | sample_count | Complexes dans ce datagramme, strictement positif |
| 68 | 4 | reserved | 0 |

La version produit V1 et la version wire v2 sont différentes. La version wire est incrémentée parce que l'amont possède déjà SDBU v1 avec une autre disposition et une autre endianness.

Taille reçue exigée : 72 + sample_count × octets_par_IQ. Rejeter magic/version/format inconnus, longueur incohérente, champs réservés non nuls et flags incohérents. HARDWARE_ORIGIN exige TIME_VALID et une provenance source réellement matérielle ; un temps dérivé par resampling peut conserver cette origine si la relation est prouvée. TIME_VALID interdit time_domain=unknown.

Les sorties sont rattachées à run_id par le canal de contrôle. Après redémarrage serveur, un client doit refaire hello/subscribe ; il ne réutilise pas une ancienne association de stream_id. Avant dépassement d'un champ de compteur, arrêter/recréer l'identité concernée avec notification ; pas de wrap silencieux.

## 5. Découverte et logiciels tiers

Proposition mDNS : service `_sdrbridge._tcp`, TXT sans secret avec `api=1`, `product`, `run_id`, `auth=required`. Le port annoncé est celui du contrôle natif. Une adresse manuelle permet de fonctionner sans multicast de découverte ; VPN et VLAN peuvent ne pas le transporter.

SDR++ 1.2.1 : identifier le module de source réseau installé et sa documentation avant de choisir RAW IQ ou un autre protocole. QMAP : définir/qualifier TIMF2 séparément. Le client Python de référence consomme SDBU v2. ANTRACK/HDSDR restent d'abord sur les interfaces locales préservées.

Une preuve de conformité réseau inclut des vecteurs binaires exacts, un parseur de référence, des entrées invalides et un flux reçu par un second processus. Les vecteurs seront produits à partir de cette table et relus indépendamment du code encodeur.
