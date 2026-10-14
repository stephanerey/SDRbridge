# NEXT_SESSION_PROMPT

## Identite et autorisation
- Projet / task memory :
- Objectif et perimetre valide (source de validation) :
- Exclusions / autorisations sensibles :
- Etat et derniere action terminee :

## Prochaine action
- prochain ensemble coherent :
- Blocages / decision humaine attendue :
- Risques et decisions actives :
- Fichiers principaux :
- Derniere verification (source, date, environnement, limites) :

## Sources ciblees
- sr_contract.json canonique / parent :
- requirement_id ouverts : exigences partielles ou defectueuses, exigences non faites, lots repair/reopened :
- preuves et tests manquants (references) :
- retours utilisateur rattaches aux requirement_id :
- loop_contract.json :
- Details a lire pour la prochaine action :

## Reprise
Appliquer SR_BOOTSTRAP.md puis lire les contrats associes et les details necessaires. Conserver toutes les exigences ouvertes, distinguer implementation_status et evidence_status. Un retour existant rouvre le lot d'origine, pas un micro-lot de substitution.
Une demande vague implique Reprise SR stricte : resumer, ne pas muter avant validation. Ce fichier n'est pas une autorisation. En cas de contradiction, verifier la source canonique. Ne recopier ni les procedures SR ni tout l'historique.

Prompt : Reprise SR stricte. Projet : <chemin>. Lis <chemin exact NEXT_SESSION_PROMPT.md> et ses contrats. Resume l'etat, ne code pas avant validation.
