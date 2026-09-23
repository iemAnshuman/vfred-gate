import json
import numpy as np
import pytest
from vfg.canary.corpus import read_corpus
from vfg.canary.margins import top_two_margins
from vfg.errors import VFGError
from vfg.manifest import file_digest, load_document

def test_frozen_pilot():
    cases=read_corpus('corpora/pilot-v1.jsonl')
    manifest=load_document('corpora/pilot-v1.manifest.json')
    assert len(cases)==48
    assert sum(c.split=='exploratory' for c in cases)==32
    assert sum(c.split=='holdout' for c in cases)==16
    assert len({c.category for c in cases})==8
    assert manifest['corpus_sha256']==file_digest('corpora/pilot-v1.jsonl')
    assert max(len(c.tokens) for c in cases)<=128

def test_group_leak_and_duplicate_rejected(tmp_path):
    rows=[c.model_dump() for c in read_corpus('corpora/pilot-v1.jsonl')[:2]]
    rows[1]['split']='holdout'
    p=tmp_path/'corpus.jsonl';p.write_text('\n'.join(json.dumps(r) for r in rows))
    with pytest.raises(VFGError,match='leaks'):read_corpus(p)
    rows[1]=rows[0];p.write_text('\n'.join(json.dumps(r) for r in rows))
    with pytest.raises(VFGError,match='duplicate'):read_corpus(p)

def test_margins():
    assert top_two_margins(np.array([[1,3,3],[1,2,5]],dtype='f4')).tolist()==[0,3]
