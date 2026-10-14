# Contrat visuel Qt — V1

À lire pour le lot UI avec S1. Application de bureau native, pas de navigateur/Playwright. Widgets Qt standards accessibles, texte français, unités affichées, distinction couleur ET texte pour les états.

## Fenêtre normale

Taille initiale1100×720 pixels logiques, minimum900×600, redimensionnable et compatible mise à l'échelle125/150/200%. Barre supérieure persistante : source sélectionnée, état textuel, fréquence effective, Démarrer/Arrêter, bouton Compact. Bandeau d'erreur non modal avec code, explication et Réessayer si applicable ; pas de boîte bloquante depuis un callback.

Navigation : Radio | Sorties et clients | Profils RF | Captures | Diagnostics. Spectre partagé sous les contrôles de Radio ; tableau clients accessible sans interrompre la réception. Une barre de statut résume débit, pertes source et alertes consommateurs, sans confondre leurs compteurs.

Radio : carte périphérique/backend et bouton Actualiser ; capacités ; fréquence/taux/BW/antenne/gains/AGC ; deux colonnes demandé/effectif lorsque différents. Les modifications restent en brouillon jusqu'à Appliquer ; désactiver pendant OPENING/RECONFIGURING/STOPPING. Une commande ancienne reçoit un conflit visible, jamais écrasement silencieux.

Sorties : tableau des profils (nom,taux,format,révision,abonnements), destinations opérateur séparées des clients connectés. Actions Ajouter/Modifier/Copier/Supprimer ; suppression d'un profil référencé refusée avec liste des usages. Une édition crée une révision ; abonnements existants restent sur leur révision jusqu'à migration explicite et atomique d'une destination.

Profils RF : tableau plage[min,max[,priorité,antenne,gains,AGC ; validation d'ambiguïtés avant sauvegarde ; état actif/suspendu et Reprendre automatique. Les profils RF ne modifient pas le taux de sortie des abonnements.

Captures : choisir source/profil, dossier, nom, Démarrer/Arrêter, taille/durée/état. Replay : fichier, infos validées, position et lecture ; passage depuis matériel impose un arrêt explicite confirmé. Ne pas auto-reprendre une capture après incident.

Diagnostics : versions, état effectif, compteurs par couche, erreurs récentes, Exporter. Ne pas afficher le token LAN ; seulement son état configuré/non configuré. Paramétrage réseau désactivé par défaut, interfaces choisies explicitement.

## Compact Monitor

Cible480×120, minimum360×100 logiques. Première ligne : état/source, fréquence, mode normal, toujours au-dessus optionnel. Deuxième : spectre réduit. Troisième : débit, nombre de clients, pertes/alerte, Stop. Pas de formulaire RF complet. La bascule conserve fenêtre/session/abonnements et service de FFT ; aucune ouverture/reconfiguration de source.

## Tests et preuves attendus

Créer tests QtTest avec source simulée : états vides/erreur/réception, conflit config, profil invalide, destination en erreur, cinq clients, capture interrompue, normal↔compact répété, restauration hors écran. Captures réelles Qt des deux modes à100% et150%, aucune troncature d'une action critique. Un rendu offscreen teste les widgets, mais ne remplace pas une inspection Windows/DPI.

Fermer la fenêtre demande confirmation uniquement si réception/capture active ; annuler conserve le flux, confirmer suit l'arrêt S5. Pas de fermeture masquée en zone de notification en V1. Le test de continuité en bascule vérifie les compteurs source, pas seulement une image de GUI.
