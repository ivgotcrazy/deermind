import json

import pytest

from architecture_validation.common import BASE,Rejected,strict_json
from architecture_validation.contracts import validate
from architecture_validation.model_output import parse_model_output,normalize_empty_extras


def cases():
    return json.loads((BASE/'fixtures/format-regression-v1.json').read_text(encoding='utf-8'))['cases']


def empty_cases():
    return json.loads((BASE/'fixtures/empty-field-regression-v1.json').read_text(encoding='utf-8'))['cases']


@pytest.mark.parametrize('case',empty_cases(),ids=lambda case:case['attempt_id'])
def test_original_empty_extra_failures_retain_all_contract_fields(case):
    raw,_=parse_model_output(case['content'])
    with pytest.raises(Rejected,match='additionalProperties.*_note'):validate(case['schema'],raw)
    output,repairs=normalize_empty_extras(raw,case['schema'])
    validate(case['schema'],output)
    assert len(repairs)==3
    for before,after in zip(raw['items'],output['items']):
        removed=set(before)-set(after)
        assert len(removed)==1
        assert before[next(iter(removed))] in (None,'')
        assert all(before[k]==v for k,v in after.items())


@pytest.mark.parametrize('unknown',[False,0,[],{},'a substantive assertion',' '])
def test_nonempty_or_typed_extras_remain_rejected(unknown):
    schema={'type':'object','properties':{'known':{'type':'string','minLength':1}},
            'required':['known'],'additionalProperties':False}
    raw={'known':'preserved','extra':unknown}
    output,repairs=normalize_empty_extras(raw,schema)
    assert output==raw and repairs==[]
    with pytest.raises(Rejected,match='additionalProperties.*extra'):validate(schema,output)
    for invalid in (None,''):
        output,repairs=normalize_empty_extras({'known':invalid},schema)
        assert output=={'known':invalid} and repairs==[]
        with pytest.raises(Rejected,match='SchemaMismatch'):validate(schema,output)


def test_empty_extra_array_schema_and_pointer_audit():
    item={'type':'object','properties':{'value':{'type':'integer'}},'additionalProperties':False}
    schema={'type':'array','prefixItems':[item],'items':item}
    raw=[{'value':1,'a/b~c':None},{'value':2,'note':''}]
    output,repairs=normalize_empty_extras(raw,schema)
    assert output==[{'value':1},{'value':2}]
    assert [r['path'] for r in repairs]==['/0/a~1b~0c','/1/note']
    assert raw[0]['a/b~c'] is None  # The raw candidate is retained.


@pytest.mark.parametrize('case',cases(),ids=lambda case:case['attempt_id'])
def test_original_failed_outputs_preserve_values_and_pass_schema(case):
    with pytest.raises(ValueError,match='DuplicateJSONKey'):strict_json(case['content'])
    parsed,audit=parse_model_output(case['content'])
    assert parsed==json.loads(case['content'])  # All duplicate values were identical.
    assert [item['path'] for item in audit['repairs']]==[f'/items/{n}/conflicts' for n in range(3)]
    validate(case['schema'],parsed)


@pytest.mark.parametrize('raw',[
    '{"x":true,"x":1}', '{"x":1,"x":"1"}', '{"x":1,"x":1.0}',
    '{"x":[1,2],"x":[2,1]}', '{"x":{},"x":[]}',
    '{"x":{"a":1},"x":{"a":2}}',
    '{"x":9007199254740992.0,"x":9007199254740993.0}',
    '{"x":{"a":1,"a":2},"x":{"a":2}}',
])
def test_conflicting_duplicates_are_never_overwritten(raw):
    with pytest.raises(ValueError,match='ConflictingJSONKey:'):parse_model_output(raw)


@pytest.mark.parametrize('raw',['{"x":NaN}','{"x":Infinity}','{"x":1e999}',
                                     '{"x":1,}', '```json\n{"x":1}\n```', '[1,2]'])
def test_invalid_output_is_not_guessed(raw):
    with pytest.raises(ValueError):parse_model_output(raw)


def test_nested_equivalence_and_json_pointer_audit():
    parsed,audit=parse_model_output('{"a/b~c":{"x":[],"y":"词"},"a/b~c":{"y":"词","x":[]}}')
    assert parsed=={'a/b~c':{'x':[],'y':'词'}}
    assert audit['repairs']==[{'operation':'coalesce_identical_duplicate','path':'/a~1b~0c'}]
    assert parse_model_output('{"amount":1.25,"count":3,"ok":true}')[0]=={'amount':1.25,'count':3,'ok':True}


@pytest.mark.parametrize('case',[cases()[0],*empty_cases()],ids=lambda case:case['attempt_id'])
def test_real_adapter_retains_raw_output_and_uses_one_http_attempt(tmp_path,monkeypatch,case):
    from architecture_validation import model as module
    payload={'choices':[{'finish_reason':'stop','message':{'content':case['content']}}],
                            'usage':{'prompt_tokens':10,'completion_tokens':20}}
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return json.dumps(payload).encode()
    opened=[]
    class Opener:
        def open(self,*args,**kwargs):opened.append(1);return Response()
    monkeypatch.setattr(module,'load_config',lambda:{'base_url':'https://api.deepseek.com','model':'deepseek-flash','api_key':'test-only'})
    monkeypatch.setattr(module.urllib.request,'build_opener',lambda *args:Opener())
    adapter=module.RealModel('B2',tmp_path/'calls',tmp_path/'budget.json')
    output,record=adapter.complete('test',{},case['schema'],'Belief')
    validate(case['schema'],output)
    assert len(opened)==1 and adapter.budget.data['total_attempts']==1
    assert record['content']==case['content'] and len(record['normalization']['repairs'])==3
    disk=json.loads((tmp_path/'calls'/(record['attempt_id']+'.json')).read_text(encoding='utf-8'))
    assert disk['content']==case['content'] and disk['normalization']==record['normalization']
    payload['choices'][0]['message']['content']='{"x":1,"x":2}'
    with pytest.raises(Rejected,match='InvalidStructuredOutput:ConflictingJSONKey:/x'):
        adapter.complete('test',{},case['schema'],'Belief')
    assert len(opened)==2  # A content conflict is not retried as a network error.
