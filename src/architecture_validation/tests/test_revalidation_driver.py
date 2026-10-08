from architecture_validation.revalidate import select_input, prepare_probe
from architecture_validation.revalidation_samples import probes
from architecture_validation.contracts import validate, WIRE


def test_display_branch_requires_actual_occurrence_on_target_turn():
    item={'text':'没有收到提示','after_display_turn':1,'with_display_text':'看过提示'}
    session={'turns':[{'id':'t1'}]}
    assert select_input(item,session,[])[1]=='no-confirmed-display'
    for kind,tid in [('ActionIntent','t1'),('ActionOccurrence','t2')]:
        assert select_input(item,session,[{'kind':kind,'turn_id':tid,'body':{'blocks':[{'text':'提示'}]}}])[1]=='no-confirmed-display'
    assert select_input(item,session,[{'kind':'ActionOccurrence','turn_id':'t1','body':{'blocks':[{'text':'提示'}]}}])==('看过提示','confirmed-display')


def test_probe_runtime_packet_excludes_answer_labels_and_binds_sources():
    for probe in probes(True):
        sem,schema,mapping=prepare_probe(probe)
        assert 'expected' not in sem and 'criterion' not in sem
        assert all(value.startswith('R') for value in mapping.values())
        validate(WIRE[probe['purpose']],sem['candidate'])
