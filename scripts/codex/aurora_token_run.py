#!/usr/bin/env python3
import argparse,subprocess,datetime,hashlib
from pathlib import Path
def compact(text, max_lines=120):
    from collections import Counter
    lines = text.splitlines()
    limit = max(8, max_lines)
    if len(lines) <= min(30, limit):
        return text if text.endswith("\n") or not text else text + "\n"
    counts = Counter(line for line in lines if any(k in line.lower() for k in
                     ('error', 'failed', 'failure', 'warning', 'traceback', 'exception', 'fatal')))
    severe = [line for line in counts if 'warning' not in line.lower() or any(k in line.lower() for k in ('error', 'fatal', 'failed', 'exception'))]
    warnings = [line for line in counts if line not in severe]
    out = [f"Compressed: {len(lines)} lines; {len(counts)} unique diagnostics. Raw log is authoritative."]
    for line in severe + warnings:
        out.append(f"[{counts[line]}x] {line}" if counts[line] > 1 else line)
    if len(out) >= limit:
        return "\n".join(out[:limit-1] + ["TRUNCATED diagnostics: inspect raw log before concluding."]) + "\n"
    tail = [line for line in lines[-10:] if line not in counts]
    out += ["Tail:"] + tail[:max(0,limit-len(out)-1)]
    return "\n".join(out) + "\n"
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--max-lines',type=int,default=120); ap.add_argument('cmd',nargs=argparse.REMAINDER); a=ap.parse_args()
    cmd=a.cmd[1:] if a.cmd and a.cmd[0]=='--' else a.cmd
    if not cmd: raise SystemExit('missing command after --')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'); slug=hashlib.sha1(' '.join(cmd).encode()).hexdigest()[:8]
    raw=Path('output/codex/raw'); comp=Path('output/codex/compact'); raw.mkdir(parents=True,exist_ok=True); comp.mkdir(parents=True,exist_ok=True)
    rp=raw/f'{stamp}_{slug}.log'; cp=comp/f'{stamp}_{slug}.summary.md'
    proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    rp.write_text(proc.stdout,encoding='utf-8'); summary=compact(proc.stdout,a.max_lines); cp.write_text(summary,encoding='utf-8')
    print(summary); print(f'\nRaw output: {rp}\nCompact output: {cp}')
    raise SystemExit(proc.returncode)
if __name__=='__main__': main()
