"""The narrow domain bootstrap; no learner conclusions or test answer labels."""
from .common import digest
from .contracts import NORM, validate


def exact(kind, ident, body, version="v1", revision=0):
    return {"kind":kind,"id":ident,"version":version,"revision":revision,"content_hash":digest(body)}


def definitions():
    result=[]
    def add(kind, ident, body, version="v1"):
        validate(NORM[kind], body)
        result.append({"kind":kind,"id":ident,"version":version,"body":body})
        return exact(kind,ident,body,version)
    family=add("TaskFamily","unit-rate",{"definition":"先求单位量再按目标数量缩放的正比例应用题", "conditions":["整数数量与总价，关系为正比例"],
        "responsibilities":["识别单位量关系","选择除后乘策略","自行计算并说明数量单位"],"quality_requirements":["关系、计算及单位合理","说明依据而非只猜最终数值"]})
    kcs=[]
    for ident,definition,effect in [("unit-relation","单位量关系","由总量与份数说明每份量"),("division","整数除法","自行求商并检查除法结果"),("scaling","按数量缩放","用单位量计算目标数量的总量")]:
        kcs.append(add("KC",ident,{"definition":definition,"application_conditions":["本 Task Family 的正整数场景"],"cognitive_effect":effect}))
    add("SolutionStrategy","unit-method",{"task_family_ref":family,"method":"总价除以数量求单位价，再乘目标数量", "steps":[
        {"id":"unit","responsibility":"求单位量","inputs":["total","quantity"],"outputs":["unit_value"]},
        {"id":"scale","responsibility":"按目标数量缩放","inputs":["unit_value","target"],"outputs":["target_total"]}],"kc_refs":kcs})
    claims=[]
    for ident,typ,scope,owned,support,quality,against in [
        ("claim-task","TaskProficiency",family,["独立识别关系、选择策略、计算及检查"],[],["相对稳定地独立完成本类任务；一次作答只能提供局部证据"],["在条件适用且无实质帮助时出现关系、策略或计算错误"]),
        ("claim-unit","KC",kcs[0],["自己说明单位量关系及为什么使用总量除以份数"],[],["能用数量意义说明单位量，不只复述系统解释"],["把总量与单位量混淆或不能说明除法意义"]),
        ("claim-division","KC",kcs[1],["自己重新计算商并检查其合理性"],["可以由他人指出需要检查除法，但不提供商或计算过程"],["计算与自查正确；给出商后的重复不等于独立计算"],["在允许支持范围内仍给出错误商或不能检查计算"]),
    ]:
        claims.append(add("Claim",ident,{"claim_type":typ,"scope_ref":scope,"conditions":["本 Task Family；解释限于已观察条件"],
          "responsibility_boundary":{"learner_owned":owned,"allowed_support":support},"quality_requirements":quality,"disconfirmation_criteria":against}))
    add("EvidenceSemantics","evidence-rules",{"applicable_claim_refs":claims,"required_context":["Observation","原始作答","Claim","实际帮助及覆盖范围"],
      "relation_criteria":{"Supports":"表现对具体 Claim 所要求责任提供支持，说明局限；非掌握判定。","Contradicts":"表现对 Claim 提供反向证据，不把单次错误直接判为不会。",
      "Discriminates":"说明材料区分哪两个有依据的解释假设。","NonInformative":"请求、缺失材料或相关责任已被替代时，对该 Claim 不足以判断；必须说明具体原因。"},
      "assistance_rules":["只以实际发生内容解释帮助；请求、选择和未展示内容不算已暴露。","同一提示可能帮助定位但没有替代计算，对不同 Claim 分开判断。",
      "新题或活动标签不能清除近期帮助。","提示前的原始表现保留原有证据意义；后续帮助不倒灌到此前作答。","未知效果保持未知；不能从缺少确认推出没显示。"]})
    add("InferenceSemantics","inference-rules",{"applicable_claim_refs":claims,
      "aggregation_rules":["结合当前有效正反 Evidence，不把单次正确或系统讲解直接等同掌握。","允许有依据的方向性认识，保留小样本与迁移限制。"],
      "dependency_rules":["同一表现的重复解释不视为独立样本；保留实际帮助和相关性。"],
      "conflict_rules":["明确相冲突的 Evidence 及原因，不平均成一个无法解释的分数。"],
      "uncertainty_rules":["证据不足可以 UNKNOWN；运行失败不属于成功的 UNKNOWN。","认识不确定性不是学习者自信心。"],
      "revision_rules":["更正后的失效 Evidence 不再作为当前依据，但历史保留。","有新材料时解释为何改变认识或保持原修订；不能默认全 UNKNOWN。"]})
    return result


def task(ident, quantity, total, target, noun="练习本"):
    family=definitions()[0]
    return {"kind":"TaskInstance","id":ident,"version":"v1","body":{
      "task_family_ref":exact(family['kind'],family['id'],family['body']),
      "statement":f"{quantity}份{noun}共{total}元，{target}份同样的{noun}多少钱？请说明计算。",
      "given_data":{"quantity":quantity,"total":total,"target":target},"applicable_conditions":["正比例；单价相同"]}}
