#!/usr/bin/env python3
"""Read-only derived views of a contract. Never creates evidence or changes schemas."""
import argparse
import json
from pathlib import Path
from sr_completion_rules import (coverage_row, derive_contract_decision, derive_gate_status,
                                 derive_closure_claim, open_requirement_ids, render_user_request_table)
from validate_sr_contract import validate

def project(data):
    if data.get('schema_version') != '3.1.0':
        raise ValueError('Derived views require schema 3.1.0; legacy contracts remain untouched')
    requests=data.get('validated_requests')
    if not isinstance(requests,list) or not requests:
        raise ValueError('validated_requests must be nonempty; no completion inferred from absence')
    decision=derive_contract_decision(requests)
    return {'status':decision,'gate':derive_gate_status(decision),'claim':derive_closure_claim(decision),
            'open_requirement_ids':open_requirement_ids(requests),
            'coverage_table':[coverage_row(r) for r in requests]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--file',required=True);ap.add_argument('--json',action='store_true')
    args=ap.parse_args();path=Path(args.file)
    try:
        data=json.loads(path.read_text());result=project(data);errors,warnings=validate(data,contract_path=path)
    except (ValueError,OSError) as exc:ap.error(str(exc))
    result.update({'contract_valid':not errors,'errors':errors,'warnings':warnings,'source':str(path)})
    if args.json:print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print(f"Contract valid: {not errors}; derived status: {result['status']}")
        print(render_user_request_table(data['validated_requests']))
        if errors:print('Validation errors:\n- '+'\n- '.join(errors))
    return 0 if not errors else 1

if __name__=='__main__':raise SystemExit(main())
