#!/usr/bin/env python3
"""Derive the explicit diagnostic stack from the current baseline build."""
from vfg.canary.corpus import read_corpus
from vfg.manifest import atomic_json,load_document

baseline=load_document('stacks/baseline.json')
case=next(c for c in read_corpus('corpora/pilot-v1.jsonl') if c.id=='c001')
baseline.update(id='seeded-layer-zero',injection={'schema_version':1,'tensor':'l_out-0','position':len(case.tokens)-1,'element':0,'delta':1000.0})
atomic_json('stacks/seeded.json',baseline)
print('stacks/seeded.json references the current baseline; diagnostic injection is explicit')
