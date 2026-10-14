# CODEBASE_MAP

Base Python sous `src/sdr_bridge` : app/GUI composent, bridge orchestre, model définit contrats, source/native_sdrplay/soapy_source acquièrent, ring/client distribuent, control/udp transportent. `sdrplay.py` n'est pas le chemin natif opérationnel à privilégier.

`native/sdrplay_bridge` : API SDRplay x64 ; `native/extio_bridge` : ExtIO Win32. `compat/` contient les adaptateurs clients à relire avant mutation. `tests/test_core.py` et `tests/test_udp.py` : baseline quatre tests. `pyproject.toml` : paquet et points d'entrée ; `native/build_native.ps1` : build natif à rendre découvrable.

Cible future : docs/product/PRD.md et docs/specs/06_IMPLEMENTATION_BASELINE.md ; source de faits : docs/work/CURRENT_STATE.md et docs/reference/PREPARATION_REPORT.md. Les modules DSP/Qt/SigMF ciblés ne sont pas encore implémentés. Le code réel reste la source finale sur l'existant.

Utiliser `CODEBASE_MAP.generated.md` pour reperer des candidats, puis lire les fichiers cibles. Regenerer uniquement si la structure a change :

```bash
python3 scripts/codex/generate_repo_map.py --root . --write
```
