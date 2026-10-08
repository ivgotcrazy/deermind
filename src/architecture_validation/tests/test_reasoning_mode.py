import json
import pytest
from architecture_validation import model
from architecture_validation.common import Rejected


@pytest.mark.parametrize('settings,thinking,effort,limit,timeout',[
    ({},'disabled',None,8192,60),
    ({'thinking':'enabled','reasoning_effort':'high','max_tokens':32768,'timeout':120},'enabled','high',32768,120),
    ({'max_tokens':32768,'timeout':120},'disabled',None,32768,120),
])
def test_request_configuration_budget_and_reasoning_audit(tmp_path,monkeypatch,settings,thinking,effort,limit,timeout):
    sent=[]
    response={'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}','reasoning_content':'provider-private-test-data'}}],
              'usage':{'prompt_tokens':10,'completion_tokens':120}}
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return json.dumps(response).encode()
    class Opener:
        def open(self,request,**kwargs):sent.append((json.loads(request.data),kwargs));return Response()
    monkeypatch.setattr(model,'load_config',lambda:{'base_url':'https://api.deepseek.com','model':'deepseek-flash','api_key':'test-only'})
    monkeypatch.setattr(model.urllib.request,'build_opener',lambda *args:Opener())
    adapter=model.RealModel('B2',tmp_path/'calls',tmp_path/'budget.json',**settings)
    output,record=adapter.complete('JSON',{'data':'same'},{'type':'object'},'review:Evidence')
    payload,kwargs=sent[0]
    assert output=={'ok':True} and kwargs['timeout']==timeout
    assert payload['thinking']=={'type':thinking} and payload['max_tokens']==limit
    if effort:
        assert payload['reasoning_effort']==effort and 'temperature' not in payload
        assert record['reasoning_content']=='provider-private-test-data'
    else:assert payload['temperature']==0 and 'reasoning_effort' not in payload
    assert 'api_key' not in record['config']
    reservation=adapter.budget.data['reservations'][record['attempt_id']]
    assert reservation['output']==limit and reservation['actual_output']==120
    assert adapter.budget.data['estimated_cny']==pytest.approx((10*2+120*8)/1_000_000)


@pytest.mark.parametrize('settings',[
    {'thinking':'arbitrary'}, {'thinking':'disabled','reasoning_effort':'high'},
    {'thinking':'enabled','reasoning_effort':'ultra'}, {'max_tokens':True}, {'max_tokens':32769}, {'timeout':0},
])
def test_invalid_configuration_rejected_before_credentials_or_budget(tmp_path,settings):
    with pytest.raises(Rejected):model.RealModel('B2',tmp_path/'calls',tmp_path/'budget.json',**settings)
    assert not (tmp_path/'budget.json').exists()
