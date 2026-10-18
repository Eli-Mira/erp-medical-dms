"""Read-only source/Git and saved-proof checks; no app imports or DB access."""
from collections import Counter
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

root = Path('C:/Desktop/Huge system')
evidence = root / 'docs/evidence/invoice-cycle'
out = evidence / 'finalization-20261018'
out.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path = evidence / 'review-input/manifest.json'
m = json.loads(manifest_path.read_bytes())
head = subprocess.run(['git','rev-parse','HEAD'], cwd=root, capture_output=True, check=True).stdout.decode().strip()
assert head == m['base'], 'HEAD changed'
assert not subprocess.run(['git','diff','--cached','--name-only'], cwd=root, capture_output=True, check=True).stdout.strip(), 'Pre-existing staged files'
tracked = set(subprocess.run(['git','ls-tree','-r','--name-only',head], cwd=root, capture_output=True, check=True).stdout.decode().splitlines())
combined = []
for name, r in m['files'].items():
    raw = (root/name).read_bytes()
    assert sha(root/name) == sha(Path(r['source'])) == r['sha256'], name
    assert len(raw) == r['bytes']
    diff = Path(r['diff']).read_bytes()
    assert sha(Path(r['diff'])) == r['diff_sha256'] and b'[OUTPUT TRUNCATED' not in diff
    oldraw = subprocess.run(['git','show',head+':'+name], cwd=root, capture_output=True, check=True).stdout if name in tracked else b''
    old = oldraw.decode().replace('\r\n','\n').splitlines(keepends=True)
    new = raw.decode().replace('\r\n','\n').splitlines(keepends=True)
    generated = list(difflib.unified_diff(old,new,fromfile='a/'+name,tofile='b/'+name,n=10))
    rendered = ''.join(row if row.endswith('\n') else row+'\n\\ No newline at end of file\n' for row in generated).encode()
    assert rendered == diff, name
    replay=[]; cursor=0; pos=2; hunks=0
    while pos < len(generated):
        h = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n',generated[pos])
        assert h
        start,count,newstart,newcount = int(h[1]),int(h[2] or 1),int(h[3]),int(h[4] or 1)
        index = start-1 if count else start
        replay.extend(old[cursor:index]); oldchunk=[]; newchunk=[]; pos+=1
        while pos < len(generated) and not generated[pos].startswith('@@'):
            row=generated[pos]
            if row[0] in ' -': oldchunk.append(row[1:])
            if row[0] in ' +': newchunk.append(row[1:])
            pos+=1
        assert len(oldchunk)==count and len(newchunk)==newcount
        assert old[index:index+count]==oldchunk
        replay.extend(newchunk); cursor=index+count; hunks+=1
    replay.extend(old[cursor:])
    assert replay==new and hunks==r['hunks']
    combined.append(('\n### FILE '+name+'; diff SHA256 '+r['diff_sha256']+'\n').encode()+diff)
for name,r in m['context'].items():
    assert sha(Path(r['path']))==r['sha256']
    assert sha(root/name)==r['sha256'], name
for name,digest in m['protected_unchanged'].items():
    assert sha(root/name)==digest, name
proof=[]
for stage,r in m['proof'].items():
    run=Path(r['run']); record=json.loads(run.read_bytes())
    assert sha(run)==r['sha256']
    assert record['exit_code']==0 and record['created'] and record['removed'] and record['unchanged'] and record['default_off_exit']==0
    assert record['before']==record['after']
    for name,digest in record['after'].items():
        assert sha(root/name)==digest, name
    for artifact,digest in record['artifacts'].items():
        assert sha(run.parent/artifact)==digest, artifact
    # Trusted pytest XML from this task's bound native run, not untrusted input.
    cases=ET.parse(run.parent/'pytest.xml').findall('.//testcase')
    identities=[(c.get('classname'),c.get('name')) for c in cases]
    assert len(identities)==len(set(identities))
    buckets=Counter('failed' if c.find('failure') is not None else 'error' if c.find('error') is not None else 'skipped' if c.find('skipped') is not None else 'passed' for c in cases)
    counts={k:buckets[k] for k in ('passed','failed','error','skipped')}
    assert counts==record['counts']==r['counts']
    proof.append({'stage':stage,'run_sha256':r['sha256'],'counts':counts,'case_identities':identities,'default_off':True,'removed':True})
combined_path=out/'review.delta.txt'
combined_path.write_bytes(b''.join(combined))
record={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'task':'invoice-collection-20261017','base':head,
        'verification_type':'read-only saved-artifact revalidation, not a new native test run','database_access':False,
        'manifest_sha256':sha(manifest_path),'source_files':list(m['files']),'file_count':len(m['files']),
        'hunks':sum(r['hunks'] for r in m['files'].values()),'raw_diff_regenerated_and_replayed':True,
        'review_delta':str(combined_path),'review_delta_sha256':sha(combined_path),'review_delta_lines':len(combined_path.read_bytes().splitlines()),
        'protected_files_unchanged':list(m['protected_unchanged']),'proof':proof,'lint_reused':m['lint'],
        'prior_review':'NO_VERDICT retained unchanged; not accepted or silently retried',
        'resume_authority':'Renewed user proceed/commit request on 2026-10-18; one current-snapshot independent judgment to close the still-open commit gate. No implementation restart or default DB recovery.'}
(out/'preflight.json').write_bytes(json.dumps(record,indent=2).encode())
print(json.dumps({k:record[k] for k in ['base','verification_type','file_count','hunks','review_delta_sha256','review_delta_lines','lint_reused']},indent=2))
print('proof:',[{k:r[k] for k in ['stage','counts','removed','default_off']} for r in proof])
