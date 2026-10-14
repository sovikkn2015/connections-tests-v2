#!/usr/bin/env python3
"""Generate run13 targeted-eval summary vs run11 baseline."""
import json, glob, os

run11 = json.load(open('eval-results-full-150-run11.json'))
run11_by_id = {r['query_id']: r for r in run11['results']}

files = sorted(glob.glob('run13-targeted/q*.json'), key=lambda f: int(os.path.basename(f)[1:].replace('.json','')))
imp = reg = still = other = 0
rows = []
bootstrap_hits = 0
for fn in files:
    qid = int(os.path.basename(fn)[1:].replace('.json',''))
    d = json.load(open(fn))
    r = d['results'][0] if d.get('results') else {}
    old = run11_by_id.get(qid, {})
    old_stat = old.get('status','?')
    new_stat = r.get('status','?')
    old_avg = old.get('avg_score', 0) or 0
    new_avg = r.get('avg_score', 0) or 0
    delta = new_avg - old_avg
    if new_stat == 'PASS' and old_stat == 'FAIL':
        imp += 1; m = 'FIXED'
    elif new_stat == 'FAIL' and old_stat == 'PASS':
        reg += 1; m = 'REGRESS'
    elif new_stat == 'FAIL':
        still += 1; m = 'STILL_FAIL'
    else:
        m = 'OK'; other += 1
    flags_joined = ' '.join(r.get('flags', []))
    has_bootstrap_flag = ('BOOTSTRAP' in flags_joined.upper()) or ('Bootstrap Note' in flags_joined)
    if has_bootstrap_flag: bootstrap_hits += 1
    rows.append((qid, r.get('level','?'), old_avg, new_avg, delta, m, r.get('tools_used',[]), has_bootstrap_flag))

out = []
out.append('# Project 006 Run 13 — Targeted Eval Summary')
out.append('')
out.append('Comparison of 40 previously-failing queries from run11 vs run13 after the BOOTSTRAP-leakage fix.')
out.append('')
out.append(f'- Total queries re-run: {len(rows)}')
out.append(f'- **FIXED (FAIL->PASS): {imp}**')
out.append(f'- Regressions (PASS->FAIL): {reg}')
out.append(f'- Still failing: {still}')
out.append(f'- Already passing (edge cases): {other}')
out.append(f'- BOOTSTRAP_LEAKAGE flags in judge output: **{bootstrap_hits}**')
out.append(f'- Estimated new overall pass rate: ~{86 + imp - reg}/150 = {(86+imp-reg)/150*100:.1f}%  (vs run11 57.3%)')
out.append('')
out.append('| Q | Lvl | Run11 | Run13 | Delta | Status | Tools | BootstrapFlag |')
out.append('|---|-----|-------|-------|-------|--------|-------|---------------|')
for r in rows:
    tools = ','.join(r[6]) if r[6] else '-'
    bs = 'YES' if r[7] else 'no'
    out.append(f'| {r[0]} | {r[1]} | {r[2]:.2f} | {r[3]:.2f} | {r[4]:+.2f} | {r[5]} | {tools} | {bs} |')
out.append('')
out.append('## Still-failing queries (for next iteration)')
out.append('')
still_failing = sorted([r for r in rows if r[5] == 'STILL_FAIL'], key=lambda x: x[3])
for r in still_failing[:10]:
    q = json.load(open(f'run13-targeted/q{r[0]}.json'))['results'][0]
    out.append(f"### Q{r[0]} (L{r[1]}) avg={r[3]:.2f}")
    out.append(f"Query: {q.get('query','')[:200]}")
    out.append(f"Flags: {q.get('flags', [])}")
    out.append(f"Tools used: {q.get('tools_used', [])}")
    out.append('')

print('\n'.join(out))
