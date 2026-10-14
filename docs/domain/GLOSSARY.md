# Glossaire métier
- IQ : un échantillon complexe contient I et Q ; sample_count ne compte pas deux valeurs scalaires.
- Taux : échantillons complexes par seconde ; fréquence RF : centre de la bande reçue, en Hz.
- Époque : période de continuité d'une source ; un retune/seek/restart en crée une nouvelle.
- Profil RF : règle d'antenne/gain/AGC selon fréquence ; ne pas confondre avec profil de sortie.
- StreamProfile : taux/format/offset/protocole d'une sortie ; plusieurs abonnements partagent le même DSP.
- Abonnement : lien source/profil/destination ; un client peut en avoir plusieurs.
- Perte inconnue : compte null, jamais zéro ; temps hôte : observation, pas temps capture matériel.
- Ring : tampon circulaire partagé ; dépassement d'un lecteur ne doit pas bloquer les autres.
