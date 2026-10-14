# S2 — Contrats du cœur, sessions et mémoire

Statut : conception proposée v0.2 ; interfaces amont à préserver selon [UPSTREAM_BASELINE](../reference/UPSTREAM_BASELINE.md). Couverture : REQ-003, REQ-007 à REQ-015, REQ-019, REQ-033 à REQ-034.

## 1. Principes d'intégration

Réutiliser les modules existants quand leurs responsabilités conviennent. Les noms suivants définissent des responsabilités et des champs, pas une obligation de créer un fichier/classe par ligne. Aucun import de Qt dans le cœur d'acquisition ou le traitement headless.

Un seul composant possède l'ouverture physique d'un appareil. Les commandes sont sérialisées ; les consommateurs ne reçoivent que des données et des états. Aucun producteur ne bloque sur le traitement d'un client, le disque ou le dessin GUI.

## 2. Modèle minimal

| Objet | Champs minimaux / règles |
|---|---|
| DeviceDescriptor | device_id stable si possible, backend, modèle, série disponible, canaux RX, statut de disponibilité ; aucun secret |
| DeviceCapabilities | plages discrètes/continues, pas, unités, gains nommés, antennes, formats et settings typés ; version de lecture |
| DeviceSession | session_id, device_id, état S1, configuration demandée/effective, config_revision, dernière erreur |
| SourceStream | source_id, session_id éventuel, type hardware/simulated/replay, canal, epoch, taux effectif, format et fréquence |
| StreamProfile | profile_id, profile_revision, output_rate_sps entier, format CS16/CF32, center_offset_hz=0, protocol ; immuable une fois publié |
| ProcessingPipeline | pipeline_id, source_id, epoch, paramètres DSP normalisés, état, références d'abonnements |
| ClientSession | client_id, nom/version déclarés, transport, adresse pair, présence monotone, rôle read ; lié à sa connexion |
| Subscription | subscription_id, client_id ou owner operator, source_id, profile_id/revision, transport/destination, état |

Une destination définie par l'opérateur peut exister sans ClientSession. Un client peut avoir plusieurs abonnements ; un abonnement désigne une seule source. Le profil décrit une sortie ; il ne possède pas le SDR et n'applique pas de réglage RF.

## 3. Blocs IQ et temps

Contrat interne cible ; il ne s'agit pas d'une extension binaire implicite du ring v1 :

| Champ | Sémantique |
|---|---|
| source_id | Identité du signal producteur, distincte du profil et de l'adresse réseau |
| epoch | Entier 64 bits identifiant une période de continuité au sein de l'instance serveur |
| sequence | Compteur de blocs de cette source/époque, commence à zéro |
| first_sample_index | Index du premier échantillon complexe dans l'époque |
| sample_count | Nombre d'échantillons complexes valides ; strictement positif |
| sample_rate_sps | Taux effectif ; ne pas reprendre une valeur demandée non appliquée |
| center_frequency_hz | Fréquence RF centrale effective, ou métadonnée de replay/simulation |
| config_revision | Révision effective ; même valeur sur tous les échantillons d'un bloc |
| sample_format | CS16 ou CF32, selon les règles S3 |
| timestamp_ns | Temps associé au premier échantillon, seulement si déclaré valide |
| time_domain | unknown, device_relative, host_monotonic, unix_utc ou replay_relative |
| timestamp_origin | hardware, host_observation ou derived ; ne pas fabriquer une précision matérielle |
| discontinuity | Indicateur et raison : start, reconfigure, source_loss, ring_overrun, dsp_drop, replay_seek |
| lost_samples | Compte connu ou null ; inconnu n'est pas zéro |
| payload | Buffer de longueur exactement sample_count × octets_par_IQ ; durée de vie définie |

Les compteurs sont en échantillons complexes, jamais en valeurs scalaires I+Q ni en octets. Dans une même époque, les index croissent. Un trou connu avance l'index du nombre perdu ; s'il est impossible de quantifier un trou source, démarrer une nouvelle époque. L'arrêt/reprise, le seek et tout changement de configuration appliqué créent également une nouvelle époque dans cette proposition conservatrice.

Un retune ne conserve donc pas artificiellement une phase ou un temps continu. Les pipelines vident leur état au changement d'époque. Le contrôleur notifie la nouvelle configuration avant les premières données concernées. Les erreurs de transport d'un consommateur ne changent pas l'époque de la source saine.

Les temps de timeout utilisent une horloge monotone injectable. Ne jamais soustraire deux timestamps issus de domaines différents. Un temps d'arrivée hôte ne vaut pas temps de capture ; une UTC estimée nécessite une relation d'horloge documentée.

## 4. Ring et bornes mémoire

Le format SDBR v1 est préservé tant que les clients natifs historiques en dépendent. Ajouter d'abord la description enrichie au contrôle/interne. Si les exigences imposent une nouvelle ABI, livrer explicitement un adaptateur ou une version parallèle et ses lecteurs avant migration ; aucun changement opportuniste du header v1.

Le writer est unique. La publication d'un slot doit permettre au lecteur de détecter une réécriture concurrente. Vérifier l'intégrité d'un bloc copié pendant le wrap du ring ; un contrôle avant copie seul n'est pas accepté comme preuve suffisante. La solution d'atomicité/mémoire interprocessus Windows et C++ sera arrêtée au lot ring après lecture des deux côtés.

Ne pas exposer une vue zéro-copie au-delà de sa durée de validité sans mécanisme de protection explicite. Le mode sûr de référence est une copie cohérente ou un protocole empêchant la réutilisation tant que la lecture n'est pas achevée, sans bloquer durablement le producteur. Ne pas promettre le zéro-copie de bout en bout.

Capacité initiale proposée du ring de test : 64 slots de 4 096 échantillons CS16. Ce sont des paramètres de test, non un plafond de clients ni une capacité universelle. Chaque file DSP/transport/recorder a une borne explicite ; documenter sa mémoire maximale avec son format et sa taille de bloc.

Lecteur lent : abandonner ses blocs devenus indisponibles, augmenter ses compteurs et reprendre au plus ancien bloc encore valide. Un timeout de lecture signifie « pas encore de bloc », pas EOF. La fermeture d'un client libère son handle ; seul le propriétaire détruit le segment partagé lorsque ses utilisateurs sont arrêtés.

## 5. Mutualisation et abonnements

Clé DSP : source_id + epoch + taux/format source effectifs + taux/format sortie + offset + version/paramètres filtre. Deux profils équivalents peuvent partager le DSP ; deux sources différentes ne le partagent jamais. Le framing/protocole et les destinations sont traités après le DSP, sauf justification mesurée.

Création d'un abonnement : valider source/profil/transport et budget ; chercher ou préparer un pipeline ; ajouter la référence seulement après succès ; démarrer l'émission ensuite. En échec, libérer tout objet préparé non partagé et conserver les abonnements existants. La dernière référence libérée ferme le pipeline ; les autres références le maintiennent.

Les demandes non supportées renvoient une erreur explicite : taux nul, non entier ou supérieur au taux source dans la V1 proposée, offset non nul, format inconnu, source inactive ou profil absent. L'upsampling n'est pas introduit sans besoin identifié. Un redémarrage de source reconstruit les traitements avec la nouvelle époque ; si un profil devient impossible, seul son abonnement passe en erreur.

## 6. Métriques

Séparer : échantillons reçus du backend ; pertes backend connues/inconnues ; blocs perdus par lecteur ring ; pertes DSP par pipeline ; datagrammes/octets émis par destination ; erreurs socket ; pertes de réception déclarées par client ; drops d'affichage ; erreurs disque.

Un compteur de couche ne s'additionne pas automatiquement aux autres : le même incident peut être observé à plusieurs endroits. Le débit est calculé sur une différence de compteurs et un intervalle monotone ; la GUI indique la fenêtre utilisée. Valeur indisponible = null/« inconnu ». Les compteurs de protocole ne sont jamais remis à zéro par le bouton de remise à zéro de l'affichage.

Journaux structurés : heure, niveau, composant, run_id, source_id/epoch si concernés, code et texte. Ne pas journaliser les payloads IQ ou jetons de session. Les journaux volumineux restent dans les fichiers de preuve et hors du contexte chargé à chaque reprise.
