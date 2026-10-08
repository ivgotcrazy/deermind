"""Versioned wire schemas. Identifiers are resolved to exact supplied refs before commit."""
from copy import deepcopy
from jsonschema import Draft202012Validator
from .common import BASE, Rejected, write_json


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def arr(items):
    return {"type": "array", "items": items}


S = {"type": "string"}
SS = arr(S)
def enum(*values):
    return {"type": "string", "enum": list(values)}


REF = obj(kind=S, id=S, version=S, revision={"type": "integer"}, content_hash=S)
# Canonical refs have version != '' and revision == 0; factual refs have both empty/0.
# Derived refs have version == '' and revision > 0. No ref uses mutable 'latest'.
DEPENDENCY = obj(source_ref=REF, use=S, mode=enum("CURRENT", "PINNED"))
SOURCE = obj(record_ref=REF, content_path=S)
CLAIM = obj(claim_type=enum("TaskProficiency", "KC"), scope_ref=REF, conditions=SS,
            responsibility_boundary=obj(learner_owned=SS, allowed_support=SS),
            quality_requirements=SS, disconfirmation_criteria=SS)
TASK_FAMILY = obj(definition=S, conditions=SS, responsibilities=SS, quality_requirements=SS)
KC = obj(definition=S, application_conditions=SS, cognitive_effect=S)
TASK = obj(task_family_ref=REF, statement=S, given_data=obj(quantity={"type":"integer"}, total={"type":"integer"}, target={"type":"integer"}), applicable_conditions=SS)
STRATEGY = obj(task_family_ref=REF, method=S, steps=arr(obj(id=S, responsibility=S, inputs=SS, outputs=SS)), kc_refs=arr(REF))
ESEM = obj(applicable_claim_refs=arr(REF), required_context=SS,
           relation_criteria=obj(Supports=S, Contradicts=S, Discriminates=S, NonInformative=S), assistance_rules=SS)
ISEM = obj(applicable_claim_refs=arr(REF), aggregation_rules=SS, dependency_rules=SS,
           conflict_rules=SS, uncertainty_rules=SS, revision_rules=SS)

OBS = obj(summary=S, work_steps=arr(obj(source_id=S, statement=S, mathematical_assessment=S)),
          request_interpretation=S, current_purpose=enum("IndependentDiagnosis", "Teaching"),
          uncertainties=SS, source_ids=SS)
EV_ITEM = obj(claim_id=S, relation=enum("Supports", "Contradicts", "Discriminates", "NonInformative"),
              interpretation=S, observation_ids=SS, source_ids=SS, assistance_ids=SS,
              coverage=enum("COMPLETE", "PARTIAL", "UNKNOWN"), assistance_relevance=S, dependencies_explanation=S)
BELIEF_ITEM = obj(claim_id=S, disposition=enum("REVISE", "UNCHANGED"),
                  assessment_kind=enum("UNKNOWN", "DIRECTIONAL"), assessment=S, uncertainty=S,
                  epistemic_status=SS, evidence_ids=SS,
                  conflicts=arr(obj(evidence_ids=SS, explanation=S)), rationale=S)
POLICY = obj(outcome=enum("Execute", "NoIntervention", "Defer"), action_type=enum("Hint", "Explanation", "Control", "None"),
             blocks=arr(obj(block_id=S, text=S)), transition=enum("Teaching", "None"), rationale=S,
             reevaluation_condition=S, source_ids=SS)
REVIEW = obj(verdict=enum("PASS", "FAIL", "UNRESOLVED"), checks=arr(obj(rule_id=S,
             verdict=enum("PASS", "FAIL", "UNRESOLVED"), reason=S, source_ids=SS)))
WIRE = {"Observation": OBS, "Evidence": obj(items=arr(EV_ITEM)), "Belief": obj(items=arr(BELIEF_ITEM)), "Policy": POLICY, "Review": REVIEW}
NORM = {"Claim":CLAIM,"TaskFamily":TASK_FAMILY,"KC":KC,"TaskInstance":TASK,"SolutionStrategy":STRATEGY,"EvidenceSemantics":ESEM,"InferenceSemantics":ISEM}

FORMAL_EVIDENCE = obj(claim_ref=REF, observation_refs=arr(REF), grounding=arr(SOURCE),
                     relation=EV_ITEM["properties"]["relation"], interpretation=S,
                     epistemic_context=obj(conditions=SS, assistance_refs=arr(REF), coverage=enum("COMPLETE","PARTIAL","UNKNOWN"),
                                           observation_interval=SS, assistance_relevance=S, dependencies_explanation=S), evidence_semantics_ref=REF)
FORMAL_BELIEF = obj(claim_ref=REF, assessment=obj(kind=enum("UNKNOWN","DIRECTIONAL"),statement=S),
                   epistemic_uncertainty=S,epistemic_status=SS,evidence_basis=arr(REF),
                   conflicts=arr(obj(evidence_refs=arr(REF),explanation=S)),
                   prior_belief_ref={"anyOf":[REF,{"type":"null"}]},inference_semantics_ref=REF,inference_rationale=S)
COMPLETION = obj(turn_id=S,input_context_ref=REF,execution_refs=arr(REF),validation_refs=arr(REF),
                 execution_status=enum("SUCCEEDED","FAILED","NON_RESOLVED"),evidence_refs=arr(REF),
                 belief_results=arr(obj(claim_ref=REF,disposition=enum("REVISE","UNCHANGED"),belief_ref=REF,reason=S)), failure_reason=S)
CANONICAL = obj(kind=S,id=S,version=S,owner=S,body={"type":"object"},content_hash=S,dependencies=arr(REF),governance_ref=REF)
PACKAGE = obj(schema_version=S,package_id=S,package_revision=S,entries=arr(CANONICAL))


def validate(schema, value):
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        error=errors[0]
        raise Rejected("SchemaMismatch:" + "/".join(map(str,error.path)) + ':' + error.validator + ':' + error.message[:400])


def check_ref(ref):
    validate(REF, ref)
    if bool(ref["version"]) and ref["revision"] or ref["revision"] < 0:
        raise Rejected("InvalidRefVersion")
    if not ref["id"] or len(ref["content_hash"]) != 64:
        raise Rejected("InvalidExactRef")


def export():
    schemas = {**NORM, **{k+"Candidate":v for k,v in WIRE.items()}, "ExactRef":REF,
               "EvidenceRecordBody":FORMAL_EVIDENCE,"BeliefRecordBody":FORMAL_BELIEF,
               "EvaluationCompletion":COMPLETION,"CanonicalPackage":PACKAGE}
    for name, schema in schemas.items():
        result=deepcopy(schema);result["$schema"]="https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(result)
        write_json(BASE/"schemas"/(name+".v1.json"),result)
    return len(schemas)
