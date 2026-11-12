[English documentation](GENERIC_SOAPY_VALIDATION.md)

# Qualification des récepteurs SoapySDR génériques

Cette procédure valide un récepteur physique avec SDRbridge 0.7.0. La détection
d'une factory SoapySDR prouve uniquement que son module logiciel a été chargé ;
elle ne prouve pas que le récepteur, le pilote constructeur ou toute la chaîne
de streaming fonctionne correctement.

Les résultats validés sont consignés dans la
[matrice de validation matérielle](../HARDWARE_COMPATIBILITY_FR.md), mise à jour
au fil des essais. SDRbridge ne contient ni limites de débit propres à un
modèle, ni contrôles inventés : l'application utilise les capacités annoncées
par le récepteur sélectionné et son module SoapySDR.

## Préparer le PC de validation

1. Installer le pilote Windows, l'API, le firmware et les images matérielles
   recommandés par le constructeur du récepteur.
2. Vérifier le fonctionnement du récepteur avec l'utilitaire du constructeur
   lorsqu'il en existe un.
3. Fermer tous les autres logiciels susceptibles d'avoir ouvert le récepteur.
4. Installer la version courante de SDRbridge. PothosSDR n'est pas nécessaire
   pour exécuter l'application distribuée.
5. Ne copier aucune DLL SoapySDR privée de SDRbridge dans PothosSDR, SDR++,
   ANTRACK ou un autre logiciel. Les piles logicielles doivent rester isolées.

SDRbridge ne télécharge, ne remplace et ne modifie aucun pilote, firmware ou
fichier d'image du constructeur. Un récepteur incorrectement configuré en
amont ne peut pas être réparé par SDRbridge.

## Exécuter le test du récepteur

1. Ouvrir SDRbridge sans démarrer l'acquisition, puis actualiser la liste des
   sources.
2. Vérifier que le récepteur apparaît et relever son libellé complet.
3. Le sélectionner et vérifier que les débits, bandes passantes, transports IQ,
   antennes, AGC et gains ne sont affichés que si le module SoapySDR les expose.
4. Commencer avec un débit prudent et appuyer sur **Acquisition**. Attendre que
   le bouton devienne vert et que le débit mesuré se stabilise.
5. Observer un spectre ou une cascade active pendant au moins 60 secondes. Le
   débit mesuré doit correspondre au débit sélectionné et les compteurs de
   pertes séparés doivent rester stables.
6. Ajouter une destination UDP locale au même débit, puis répéter l'observation.
7. Changer de fréquence et essayer chaque gain ou contrôle AGC visible.
   L'absence d'un contrôle n'est pas un défaut si le matériel ne l'annonce pas.
8. Effectuer cinq cycles Stop/Play, passer temporairement en Simulation, puis
   revenir au récepteur. L'acquisition doit repartir sans rester sur « waiting
   for new blocks ».
9. Augmenter progressivement le débit source. Lorsque plusieurs transports IQ
   sont annoncés, tester **Auto** et chaque transport explicite pertinent.
10. Tester pendant au moins cinq minutes la combinaison de clients prévue, y
    compris les sorties filtrées à débit inférieur.
11. Exporter le ZIP de diagnostic et capturer les pages **Radio** et
    **Clients et flux**.

## Interpréter les compteurs

- Les **pertes source** sont signalées avant le traitement SDRbridge par le
  récepteur ou son pilote.
- Les **pertes de file, DSP et profil** indiquent que SDRbridge n'a pas pu
  traiter un bloc à temps.
- Les **pertes ou erreurs UDP** concernent la file d'une destination, le socket
  ou le réseau.

Le rapport de test doit conserver ces catégories au lieu de les regrouper dans
un nombre unique sans explication.

## Consigner le résultat

Pour chaque récepteur, relever le modèle et le tuner, la version du pilote ou de
l'API, le backend SoapySDR, le libellé SDRbridge complet, les débits essayés, le
transport IQ effectif, les contrôles visibles, le résultat Stop/Play, les
compteurs de pertes finaux et le rapport de diagnostic.

Seules les configurations réellement mesurées doivent entrer dans la matrice
matérielle. Le « débit IQ maximal testé » constitue une preuve obtenue avec un
récepteur et un PC donnés ; ce n'est pas nécessairement la limite absolue du
récepteur.
