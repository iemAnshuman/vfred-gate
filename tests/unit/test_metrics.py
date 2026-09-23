import numpy as np
import pytest
from vfg.compare.metrics import numeric_errors,sequence_difference,compare_rule,aligned_rows
from vfg.schema import Rule,Contract
from vfg.contracts import evaluate_contract
from vfg.errors import InsufficientEvidence,VFGError

def output(values,history=None,stop="token_budget"):
    x=np.asarray(values,dtype="<f4")
    selected=np.argmax(x,axis=1).tolist()
    return {"case_id":"a","model":{"vocab_size":x.shape[1]},"selected_tokens":selected,"stop_reason":stop,
            "steps":[{"step":i,"history_sha256":(history or ["same"]*len(x))[i],"selected_token":t}
                     for i,t in enumerate(selected)]},x

def test_ulp_and_signed_zero():
    a=np.array([-1,-0.,0.,1],dtype="<f4");b=np.nextafter(a,np.float32(np.inf))
    assert numeric_errors(a,b)["max_ulp_error"]==1
    r=numeric_errors(np.array([-0.],dtype="<f4"),np.array([0.],dtype="<f4"))
    assert r["max_ulp_error"]==0 and r["bit_equal_rate"]==0
    assert numeric_errors(np.array([-1e-45],dtype="<f4"),np.array([1e-45],dtype="<f4"))["max_ulp_error"]==2

def test_nonfinite_and_shape():
    with pytest.raises(InsufficientEvidence): numeric_errors([float("nan")],[float("nan")])
    with pytest.raises(InsufficientEvidence): numeric_errors([float("inf")],[float("inf")])
    with pytest.raises(VFGError): numeric_errors([1,2],[1])

def test_relative_and_absolute():
    r=numeric_errors([0,2],[1,3],epsilon=.5)
    assert r["max_absolute_error"]==1
    assert r["max_relative_error"]==2

def test_alignment_stops_after_first_choice_difference():
    a,x=output([[3,2],[3,2],[3,2]],["h0","h1","left"])
    b,y=output([[3,2],[2,3],[2,3]],["h0","h1","right"])
    assert aligned_rows(a,b,"free_run")==[0,1]
    rule=Rule(id="argmax",metric="argmax_agreement_rate",operator="ge",threshold=1.)
    assert compare_rule(rule,[(a,b,x,y)])["value"]==.5
    assert sequence_difference(a,b)==1
    with pytest.raises(InsufficientEvidence): aligned_rows(a,b,"teacher_forced_baseline")

def test_ties_topk_and_termination():
    a,x=output([[2,2,1]])
    b,y=output([[2,1,2]])
    r=Rule(id="topk",metric="topk_jaccard",operator="ge",threshold=0.,k=2)
    assert compare_rule(r,[(a,b,x,y)])["value"]==pytest.approx(1/3)
    assert sequence_difference(a,a) is None
    assert sequence_difference(a,a|{"stop_reason":"eos"})==1

def test_greedy_data_integrity():
    a,x=output([[3,2]]);b=a|{"selected_tokens":[1]}
    rule=Rule(id="argmax",metric="argmax_agreement_rate",operator="ge",threshold=1.)
    with pytest.raises(VFGError): compare_rule(rule,[(a,b,x,x)])

def test_four_verdicts_and_precedence():
    c=Contract(id="c",compatibility_level="decision",rules=[
        Rule(id="r",metric="argmax_agreement_rate",operator="ge",threshold=1.)])
    m=[{"id":"r","passed":True}]
    assert evaluate_contract(c,{},m).exit_code==0
    assert evaluate_contract(c,{},[{"id":"r","passed":False}]).exit_code==2
    assert evaluate_contract(c,{"insufficient":["unstable"]},m).exit_code==3
    assert evaluate_contract(c,{"errors":["corrupt"],"insufficient":["unstable"]},m).exit_code==4
    assert evaluate_contract(c,{},[]).exit_code==3

