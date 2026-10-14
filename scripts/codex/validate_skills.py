#!/usr/bin/env python3
import argparse,re,sys
from pathlib import Path
def desc_text(lines,i):
    first=lines[i].split(':',1)[1].strip()
    if first and first not in ('>-','|'): return first.strip('"')
    out=[]
    for line in lines[i+1:]:
        if line.startswith('  '): out.append(line.strip())
        else: break
    return ' '.join(out)
def validate(path):
    e=[]; f=path/'SKILL.md'
    if not f.exists(): return [f'{path}: missing SKILL.md']
    lines=f.read_text(encoding='utf-8').splitlines()
    if not lines or lines[0] != '---': return [f'{f}: missing frontmatter']
    keys=[]; name=None; desc=None
    for i,line in enumerate(lines[1:],1):
        if line == '---': break
        if ':' in line and not line.startswith(' '):
            k=line.split(':',1)[0].strip(); keys.append(k)
            if k=='name': name=line.split(':',1)[1].strip().strip('"')
            if k=='description': desc=desc_text(lines,i)
    extra=[k for k in keys if k not in ('name','description')]
    if extra: e.append(f'{f}: unsupported frontmatter fields {extra}')
    if not name: e.append(f'{f}: missing name')
    elif not re.match(r'^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$',name): e.append(f'{f}: invalid name {name}')
    if not desc: e.append(f'{f}: missing description')
    elif len(desc)>1024: e.append(f'{f}: description too long {len(desc)}')
    elif len(desc)<120: e.append(f'{f}: description too short {len(desc)}; explain role, triggers and validation context')
    agent_yaml=path/'agents'/'openai.yaml'
    if not agent_yaml.exists():
        e.append(f'{path}: missing agents/openai.yaml')
    else:
        txt=agent_yaml.read_text(encoding='utf-8')
        m=re.search(r'^\s*short_description:\s*["\']?(.+?)["\']?\s*$',txt,re.M)
        if not m:
            e.append(f'{agent_yaml}: missing interface.short_description')
        else:
            short=m.group(1).strip().strip('"').strip("'")
            if len(short)<25 or len(short)>64:
                e.append(f'{agent_yaml}: short_description length {len(short)} outside 25-64 characters')
    return e
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--path',default='skills-method'); a=ap.parse_args(); base=Path(a.path).expanduser()
    if not base.exists(): sys.exit(f'missing path: {base}')
    errs=[]; skills=[p for p in base.iterdir() if p.is_dir()]
    for p in skills: errs += validate(p)
    if errs: print('\n'.join(errs)); sys.exit(1)
    print(f'OK: {len(skills)} skill(s) valid')
if __name__=='__main__': main()
