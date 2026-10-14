# S3 — Traitement IQ et resampling

Statut : paramètres techniques proposés v0.2 ; décision P-09/P-10 à valider au lot DSP. Couverture : REQ-010 à REQ-014. Ne pas choisir une bibliothèque avant inventaire des dépendances et mesure des besoins.

## 1. Formats numériques

CS16 : paires intercalées I puis Q, deux entiers signés 16 bits en little-endian, 4 octets par échantillon complexe. CF32 : paires I puis Q IEEE-754 32 bits little-endian, 8 octets par complexe. Ces formats de payload ne suivent pas l'endianness du header réseau S4.

Conversion CS16 vers flottant : chaque composante divisée par 32768. Conversion flottant vers CS16 : multiplier par 32768, arrondir au plus proche avec égalités vers l'entier pair, saturer dans [-32768, 32767]. Valeurs non finies : refuser le bloc et compter une erreur DSP, sans propager NaN/Inf dans les clients.

Ne pas normaliser automatiquement chaque bloc par son maximum : cela détruirait l'information d'amplitude. Aucun AGC logiciel implicite. L'affichage peut utiliser une échelle relative, mais ne prétend pas à des dBm calibrés sans procédure de calibration.

Vecteurs minimaux : zéro ; composantes -1, -0,5, 0, +0,5, +1 en flottant ; valeurs hors plage ; impulsion ; sinus complexe positif et négatif. Vérifier signe, ordre I/Q, saturation, endianness et absence de conjugaison.

## 2. Resampling streaming

V1 proposée : taux entiers strictement positifs, sortie ≤ entrée, offset nul. Réduire le rapport sortie/entrée en fraction L/M. Maintenir phase et historique FIR entre blocs ; ne jamais resampler chaque bloc indépendamment avec remise à zéro du filtre.

Profils de test : 2 000 000 → 192 000 et 2 000 000 → 96 000 échantillons complexes/s. Les rapports doivent être exacts à long terme ; le découpage des blocs d'entrée ne doit pas changer les échantillons de sortie, hormis la tolérance numérique de la précision retenue.

Proposition de gabarit : bande utile |f| ≤0,40 Fs_sortie ; transition jusqu'à 0,50 Fs_sortie ; réjection ≥80 dB dans la bande arrêt ; ondulation ≤0,1 dB dans la bande utile. Ce gabarit s'évalue sur la réponse du filtre en précision suffisante. Les essais CS16 utilisent séparément une tolérance liée à la quantification et ne prétendent pas garantir 80 dB pour tout niveau d'entrée.

Préférer un filtre FIR/polyphase éprouvé. Choisir sa longueur et sa fenêtre selon le gabarit et le coût mesuré, pas une constante arbitraire copiée d'un exemple. Aucune interpolation linéaire seule ne satisfait ce contrat de réduction de taux.

Même taux et même format : chemin sans resampling. Même taux avec format différent : conversion seule. Réduire le nombre de canaux n'est pas un resampling ; aucune sommation de sources n'est autorisée.

## 3. Continuité et retard

Une époque nouvelle réinitialise l'état du filtre et la phase. La stratégie proposée est d'écarter le transitoire initial insuffisamment alimenté, de consigner le nombre d'échantillons concernés et d'aligner le premier échantillon publié avec son temps effectif. Le calcul précis du retard dépend du filtre choisi et doit être documenté avant acceptation.

Un trou connu dans l'entrée ne doit pas être comblé par interpolation silencieuse. Réinitialiser l'état, indiquer la discontinuité et reprendre une sortie propre. Les index de sortie et leur relation rationnelle aux index source sont maintenus ; le timestamp de sortie correspond au premier échantillon utile après compensation du retard connue.

Si le temps source n'est pas valide, le temps sortie ne devient pas matériel par calcul. Un timestamp dérivé conserve le domaine et la provenance de sa source. L'écart de comptage admissible en fin d'essai est exactement celui expliqué par l'amorçage et le flush documentés ; pas de dérive cumulative tolérée.

## 4. Vérification avant clients réels

Exécuter AC-08 avec une entrée identique découpée en blocs uniformes puis irréguliers. Mesurer la réponse du filtre, injecter des tonalités dans les deux côtés du spectre et des tonalités hors bande qui pourraient se replier. Vérifier les compteurs à long terme et la rupture volontaire d'une époque.

Comparer un pipeline partagé à deux calculs de référence indépendants : sorties numériques équivalentes, un seul traitement réellement instancié pour les abonnements équivalents. Établir ensuite la charge CPU du profil testé sur la machine réelle ; un filtre correct mais trop coûteux n'est pas accepté comme solution de production.
