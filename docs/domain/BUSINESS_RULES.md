# Invariants métier
1. RX seulement ; jamais d'ouverture TX. Une seule source active en V1.
2. Aucun client ne retune, ne change les gains ni ne récupère l'autorité RF.
3. Configuration effective distincte de demandée ; nouvelle époque aux frontières non continues.
4. Pas de plafond fixe de quatre clients ; buffers toujours bornés et pertes attribuées.
5. Pas de mélange de sources/époques dans un pipeline ; resampling filtré avec état entre blocs.
6. Aucun protocole présenté compatible sans version, parcours et preuve correspondants.
7. Enregistrement indépendant ; disque lent n'arrête pas la réception ; pas d'effacement automatique.
8. Réseau désactivé par défaut, LAN/VPN seulement. Ne jamais exposer un token en logs.
9. Contrat d'exécution détaillé et choix fermés : S6 ; ambiguïté factuelle remontée avec preuve.
