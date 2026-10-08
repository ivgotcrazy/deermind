from architecture_validation.common import BASE,Rejected,dumps
from architecture_validation.model import RealModel
from architecture_validation.store import Store
from architecture_validation.runtime import Engine
from architecture_validation.runtime import source_ids
from architecture_validation.testing import ScriptedModel
from architecture_validation.domain import task


def test_token_estimate_four_turns_without_api(tmp_path):
    import math
    st=Store(tmp_path/'capacity.sqlite');st.bootstrap();q=st.canonical(task('capacity',6,42,15,'本'));st.start_session('s')
    # Construct official tokenizer without loading credentials or any transport.
    from tokenizers import Tokenizer
    tokenizer=Tokenizer.from_file(str(BASE/'fixtures/deepseek-v4-tokenizer.json'))
    model=ScriptedModel();original=model.complete;bounds=[]
    def measure(system,ctx,schema,purpose,category='base'):
        texts=[system+'\n输出 JSON schema：'+dumps(schema),dumps(ctx)]
        bounds.append(math.ceil(sum(len(tokenizer.encode(v,add_special_tokens=False).ids) for v in texts)*1.25)+512)
        return original(system,ctx,schema,purpose,category)
    model.complete=measure;engine=Engine(st,model,test_mode=True)
    for n in range(4):
        t=st.enqueue('s',str(n),'42÷6＝7，7×15＝105。',q);st.claim_turn(engine.worker_epoch);engine.process(t['id'])
        assert st.turn(t['id'])['status']=='COMPLETED'
    assert len(bounds)==32 and max(bounds)<16000


def test_exact_alias_binding(tmp_path):
    import pytest
    st=Store(tmp_path/'alias.sqlite');st.bootstrap();ids=[r['id'] for r in st.rows('Claim',current=True)]
    assert source_ids(st,ids,['claim-task','Claim:claim-unit:v1'])==['Claim:claim-task:v1','Claim:claim-unit:v1']
    with pytest.raises(Rejected):source_ids(st,ids,['invented'])
    proposal=next(p for p in __import__('architecture_validation.domain',fromlist=['definitions']).definitions() if p['id']=='claim-task');proposal['version']='v2'
    new=st.canonical(proposal,activate=False)
    with pytest.raises(Rejected):source_ids(st,ids+[new],['claim-task'])


def test_short_references_bind_exact_versions_across_four_turns(tmp_path):
    st=Store(tmp_path/'derived-alias.sqlite');st.bootstrap();q=st.canonical(task('d',6,42,15));st.start_session('s')
    model=ScriptedModel();original=model.complete
    def aliases(system,ctx,schema,purpose,category='base'):
        output,record=original(system,ctx,schema,purpose,category)
        if purpose in ('Belief','Evidence'):
            assert all(c['id'].startswith('R') and 'object_id' not in c for c in ctx['claims'])
            assert 'claim-task:v1' not in dumps(ctx) and 'canonical:' not in dumps(ctx)
            assert schema['properties']['items']['items']['properties']['claim_id']['enum']==[c['id'] for c in ctx['claims']]
        return output,record
    model.complete=aliases;engine=Engine(st,model,test_mode=True)
    for n in range(4):
        t=st.enqueue('s',str(n),'新作答',q);st.claim_turn(engine.worker_epoch);engine.process(t['id'])
        assert st.turn(t['id'])['status']=='COMPLETED'
    assert len(st.rows('Decision','s'))==4
    assert max(r['revision'] for r in st.rows('Belief','s'))==4
    for r in st.rows('Evidence','s'):
        assert st.resolve(r['body']['claim_ref'])['kind']=='Claim'
        assert all(st.resolve(ref)['kind']=='Observation' for ref in r['body']['observation_refs'])


def test_constructed_or_wrong_kind_model_reference_never_commits(tmp_path):
    for bad in ('claim-task:v1','Claim:claim-task:v1','claim-task','R999','event'):
        st=Store(tmp_path/(bad.replace(':','_')+'.sqlite'));st.bootstrap();q=st.canonical(task('d',6,42,15));st.start_session('s')
        model=ScriptedModel();original=model.complete
        def corrupt(system,ctx,schema,purpose,category='base'):
            output,record=original(system,ctx,schema,purpose,category)
            if purpose=='Evidence':output['items'][0]['claim_id']=ctx['current_input_id'] if bad=='event' else bad
            return output,record
        model.complete=corrupt;engine=Engine(st,model,test_mode=True)
        t=st.enqueue('s','1','输入',q);st.claim_turn(engine.worker_epoch);engine.process(t['id'])
        assert st.turn(t['id'])['status']=='FAILED' and not st.rows('Evidence','s') and not st.rows('Decision','s')
