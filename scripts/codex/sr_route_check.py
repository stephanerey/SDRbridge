#!/usr/bin/env python3
"""Validate reachability of SR procedures; read only, both source and installed layouts."""
import argparse
import json
from pathlib import Path

REQUIRED = {'authority','evidence','impact','propagation','ui','passes','execution','memory','verification','build','resume'}

def check(root):
    base=root/'core' if (root/'core/SR_BOOTSTRAP.md').exists() else root/'docs/codex'
    errors=[]
    try:data=json.loads((base/'SR_ROUTES.json').read_text())
    except (ValueError,OSError) as exc:return [str(exc)]
    if data.get('schema_version') != 2 or not data.get('policy'):errors.append('invalid route policy')
    sources=set()
    for route in data.get('routes',[]):
        if not route.get('trigger'):errors.append('route missing trigger')
        for rel in route.get('sources',[]):
            p=Path(rel)
            if p.is_absolute() or '..' in p.parts:errors.append(f'unsafe route {rel}');continue
            if not (base/p).is_file():errors.append(f'missing routed procedure {rel}')
            sources.add(p.stem)
    for name in sorted(REQUIRED-sources):errors.append(f'unreachable required procedure: {name}')
    return errors

def routed_text(root,relative):
    """Legacy marker checks follow the canonical route instead of requiring duplicate prose."""
    text=(root/relative).read_text(encoding='utf-8')
    routed={'AGENTS.md','AGENTS.template.md','SR_BOOTSTRAP.md','SR_HARNESS_METHOD.md','LOT_EXECUTION_METHOD.md','WORKFLOW_CODEX.md'}
    if Path(relative).name not in routed:return text
    base=root/'core' if (root/'core/SR_BOOTSTRAP.md').exists() else root/'docs/codex'
    if not (base/'SR_ROUTES.json').exists():return text
    text+='\n'+(base/'SR_BOOTSTRAP.md').read_text()
    data=json.loads((base/'SR_ROUTES.json').read_text())
    for rel in sorted({s for r in data['routes'] for s in r['sources']}):
        if (base/rel).is_file():text+='\n'+(base/rel).read_text()
    return text

def select(root, events):
    base=root/'core' if (root/'core/SR_BOOTSTRAP.md').exists() else root/'docs/codex'
    data=json.loads((base/'SR_ROUTES.json').read_text())
    by_event={r['event']:r for r in data['routes']}
    unknown=set(events)-set(by_event)
    if unknown: raise ValueError('Unknown events; do not infer not_applicable: '+', '.join(sorted(unknown)))
    return {'events':events,'sources':sorted({s for event in events for s in by_event[event]['sources']}),
            'notice':'Explicit events are classified by the agent from evidence. Reevaluate after discoveries. This is not a gate result or authorization.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='.')
    ap.add_argument('--events',nargs='+',help='Explicit task events; unknown events fail closed')
    args=ap.parse_args();root=Path(args.root)
    errors=check(root)
    if errors:print(json.dumps({'ok':False,'errors':errors}));return 1
    try:result=select(root,args.events) if args.events else {'ok':True,'errors':[]}
    except ValueError as exc:ap.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
