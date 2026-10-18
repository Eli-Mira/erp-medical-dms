"""Bind a completed disposable native run to the frozen candidate; no DB access."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

root=Path('C:/Desktop/Huge system')
e=root/'docs/evidence/invoice-cycle'
stage=sys.argv[1]
assert re.fullmatch(r'[a-zA-Z0-9_-]+',stage)
rpath=e/stage/'run.json'
r=json.loads(rpath.read_bytes())
m=json.loads((e/'review-input/manifest.json').read_bytes())
assert r['exit_code']==0 and r['created'] and r['removed'] and r['unchanged'] and r['default_off_exit']==0
assert r['before']==r['after']
for p,digest in r['after'].items():
    assert hashlib.sha256((root/p).read_bytes()).hexdigest()==digest,p
for p,v in m['files'].items():
    assert r['after'][p]==v['sha256'],p
for artifact,digest in r['artifacts'].items():
    assert hashlib.sha256((rpath.parent/artifact).read_bytes()).hexdigest()==digest
# Trusted XML from this task's locally executed, hash-bound pytest process.
cases=ET.parse(rpath.parent/'pytest.xml').findall('.//testcase')
ids=[c.get('classname','')+'::'+c.get('name','') for c in cases]
assert len(ids)==len(set(ids))
assert all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases)
assert r['counts']=={'passed':len(ids),'failed':0,'error':0,'skipped':0}
old=json.loads((e/'final-full-suite/run.json').read_bytes())
old_ids=[c['id'] for c in old['cases']]
# These three parameters are uuid4() values created during collection (source lines 324-326).
pattern=r'^(tests\.test_invoice_cycle_safety::test_receipt_rejects_malformed_or_forged_fields\[(?:customer_id|branch_id|created_by)-)[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\]$'
def identity(value):
    return re.sub(pattern,r'\1<generated-uuid4>]',value)
assert sum(bool(re.fullmatch(pattern,x)) for x in old_ids)==3
assert sum(bool(re.fullmatch(pattern,x)) for x in ids)==3
assert len(set(map(identity,ids)))==len(ids)
assert Counter(map(identity,ids))==Counter(map(identity,old_ids))
assert old['after']==r['after']
assert len(ids)==315
p={'verdict':'PASS','phase':stage,'verification':'fresh native full-suite execution, direct pytest exit 0; parent raw-record validation',
   'base_commit':m['base'],'candidate_commit':None,'candidate_state':'working-tree candidate; final Git commit binding is a separate readback',
   'source_sha256':{p:v['sha256'] for p,v in m['files'].items()},'run':str(rpath),
   'run_sha256':hashlib.sha256(rpath.read_bytes()).hexdigest(),'counts':r['counts'],
   'exact_raw_case_identities_match':Counter(ids)==Counter(old_ids),'same_315_semantic_case_identities':True,
   'identity_comparison':{'source':'tests/test_invoice_cycle_safety.py:324-326','normalization':'Only the three named forged-field UUIDv4 parameter values; raw IDs retained in both native records.',
       'old_only':list((Counter(old_ids)-Counter(ids)).elements()),'new_only':list((Counter(ids)-Counter(old_ids)).elements()),
       'initial_validator_failure':'Exact UUID parameter IDs differed across process collections; coordinator comparison error, not pytest/application RED. No source or tests changed.'},
   'protected_files_unchanged':list(m['protected_unchanged']),'default_off':True,'disposable_database_removed':r['database'],
   'parent_validation_database_access':False,'scope':'Current candidate code only; historical isolation incident/default DB recovery not waived.'}
out=e/'finalization-20261018'/(stage+'-verification.json')
assert not out.exists()
out.write_bytes(json.dumps(p,indent=2).encode())
print(json.dumps({k:p[k] for k in ['verdict','phase','counts','same_315_semantic_case_identities','default_off','disposable_database_removed']},indent=2))
