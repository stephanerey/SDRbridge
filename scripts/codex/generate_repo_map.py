#!/usr/bin/env python3
import argparse
from pathlib import Path
IGNORE={'.git','node_modules','.next','dist','build','__pycache__','.venv','venv','output','tasks'}
def files(root,patterns,limit=300):
    out=[]
    for pat in patterns:
        for p in root.rglob(pat):
            if any(part in IGNORE for part in p.parts): continue
            if p.is_file() and not p.name.startswith('test_'): out.append(p)
    return sorted(set(out))[:limit]
def rel(p,root): return str(p.relative_to(root)).replace('\\','/')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--write',action='store_true'); ap.add_argument('--root',default='.'); a=ap.parse_args(); root=Path(a.root).resolve()
    frontend=files(root,['page.tsx','layout.tsx','route.ts'],400)
    backend=files(root,['*.py'],400)
    migrations=files(root,['*/versions/*.py','*alembic*.py'],200)
    runtime=files(root,['package.json','pyproject.toml','requirements.txt','docker-compose*.yml','Dockerfile*'],100)
    lines=['# CODEBASE_MAP.generated.md','', '> Genere automatiquement. Ne pas editer manuellement.', '', '## Frontend route candidates']
    lines += [f'- `{rel(p,root)}`' for p in frontend]
    lines += ['', '## Backend Python candidates'] + [f'- `{rel(p,root)}`' for p in backend]
    lines += ['', '## Migration candidates'] + [f'- `{rel(p,root)}`' for p in migrations]
    lines += ['', '## Build/runtime files'] + [f'- `{rel(p,root)}`' for p in runtime]
    txt='\n'.join(lines)+'\n'; target=root/'docs/codex/CODEBASE_MAP.generated.md'
    if a.write: target.parent.mkdir(parents=True,exist_ok=True); target.write_text(txt,encoding='utf-8'); print('wrote',target)
    else: print(txt)
if __name__=='__main__': main()
