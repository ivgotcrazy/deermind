"""Declared top-level field uses and exact provenance; never classify text meaning."""
from hashlib import sha256
from dataclasses import is_dataclass
import json

from .records import Ref,Space,json_value
from .runtime import ContractError

FORMAT='declared-fields-v1'


def fingerprint(value):
    return sha256(json.dumps(json_value(value) if is_dataclass(value) else value,
                            sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()


def exact(value):
    if not isinstance(value,dict) or set(value)!={'space','identity','revision'}:
        raise ContractError('InvalidProjectionContractRef')
    try:ref=Ref(Space(value['space']),value['identity'],value['revision'])
    except (ValueError,TypeError):raise ContractError('InvalidProjectionContractRef') from None
    if ref.space!=Space.CANONICAL:raise ContractError('CanonicalProjectionContractRequired')
    return ref


def check_profile(profile,allowed_kinds):
    if (not isinstance(profile,dict) or set(profile)!={'format','inputs'} or profile['format']!=FORMAT
            or not isinstance(profile['inputs'],list) or not profile['inputs']):
        raise ContractError('InvalidContextProjectionProfile')
    kinds=[]
    for row in profile['inputs']:
        if not isinstance(row,dict) or set(row)!={'kind','mode','contract','fields','use'}:
            raise ContractError('InvalidProjectionInput')
        if row['kind'] not in allowed_kinds or row['mode'] not in ('formal','source'):
            raise ContractError('InvalidProjectionKindOrMode')
        fields=row['fields']
        if (not isinstance(fields,list) or not fields or any(not isinstance(f,str) or not f for f in fields)
                or len(fields)!=len(set(fields)) or not isinstance(row['use'],str) or not row['use']):
            raise ContractError('InvalidProjectionFieldsOrUse')
        exact(row['contract']);kinds.append(row['kind'])
    if len(kinds)!=len(set(kinds)) or set(kinds)!=set(allowed_kinds):
        raise ContractError('IncompleteOrDuplicateProjectionKinds')


def formal_proof(boundary,record,contract_ref):
    if record.ref.space!=Space.DERIVED:raise ContractError('FormalProjectionRequiresCommittedDerived')
    for candidate in boundary._candidates.values():
        if candidate.record.ref!=record.ref or candidate.protocol!=contract_ref:continue
        digest=fingerprint(candidate)
        if ('candidate-sha256:'+digest not in record.provenance or candidate.record.payload!=record.payload):continue
        commits=[r for r in boundary.h.audit.records(record.subject) if r.kind=='CommitOutcome'
                 and r.payload.get('status')=='Committed' and r.payload.get('candidate_digest')==digest
                 and r.payload.get('committed')==json_value(record.ref)]
        reviews=[r for r in boundary._reviews.values() if r.identity in record.provenance
                 and r.candidate_digest==digest and not boundary.validate(candidate,r.identity)]
        if commits and reviews:
            return {'candidate_digest':digest,'commit_ref':json_value(commits[0].ref),
                    'validation_ref':json_value(reviews[0].execution),'rule_ref':json_value(reviews[0].rule)}
    raise ContractError('ProjectionFormalCommitProofMissing')


def project(boundary,record,rule,contract,consumer_ref):
    if rule['mode']=='formal':
        if contract.kind!='ReasoningProtocol':raise ContractError('ProjectionProducerProtocolRequired')
        proof=formal_proof(boundary,record,contract.ref)
        uses=contract.payload.get('output_field_uses')
    else:
        if (contract.kind!='ContentUseContract' or record.ref.space==Space.DERIVED
                or contract.payload.get('record_kind')!=record.kind
                or contract.payload.get('record_space')!=record.ref.space.value):
            raise ContractError('ProjectionSourceContractMismatch')
        uses=contract.payload.get('field_uses');proof=None
    if not isinstance(uses,dict):raise ContractError('DeclaredOutputFieldUsesRequired')
    fields=rule['fields']
    for field in fields:
        allowed=uses.get(field)
        if (field not in record.payload or not isinstance(allowed,list) or not allowed
                or any(not isinstance(u,str) or not u for u in allowed) or rule['use'] not in allowed):
            raise ContractError('FieldUseNotAdmitted')
    content={field:record.payload[field] for field in fields}
    metadata={'format':FORMAT,'record_ref':json_value(record.ref),'source_payload_sha256':fingerprint(record.payload),
        'projected_payload_sha256':fingerprint(content),'fields':fields,'use':rule['use'],'mode':rule['mode'],
        'contract_ref':json_value(contract.ref),'consumer_protocol':json_value(consumer_ref),'formal_proof':proof}
    return json.dumps(content,sort_keys=True,ensure_ascii=False),json.dumps(metadata,sort_keys=True,ensure_ascii=False)
