import pytest
from architecture_validation.common import Rejected, write_json
from architecture_validation.model import Budget


def test_new_campaign_budget_cannot_spend_past_development_round(tmp_path):
    path=tmp_path/'budget.json';b=Budget(path)
    b.data['policy']={'category_limits':{'B2':160,'base':240,'repair':24,'probe':12,'transport':24},
                      'total_attempts':460,'development_segment_attempts':80,'active_all_phases':True}
    b.data['segment_counts']={'dev-01':80};b.save();b=Budget(path);b.segment='dev-01'
    with pytest.raises(Rejected,match='DevelopmentRoundBudgetExhausted'):b.reserve('B2','base',1,1,'x')
    b.segment='dev-02';attempt=b.reserve('B2','base',1,1,'x')
    assert b.data['reservations'][attempt]['segment']=='dev-02'
    b.data['total_attempts']=460
    with pytest.raises(Rejected,match='CallBudgetExhausted'):b.reserve('B4','base',1,1,'x')
