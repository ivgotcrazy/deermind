"""One context-local model vocabulary; exact identities remain backend-owned."""
from copy import deepcopy

from .common import Rejected


class Bindings:
    def __init__(self, store, context):
        self.store = store
        self.semantic = context['body']['semantic']
        self.rows = {rid: store.get(rid) for rid in context['body']['control']['refs']}
        # Stable within this database, while only this context's listed tokens are
        # selectable. Re-reading prior prose cannot silently rebind an old token.
        self.encode = {rid: f'R{row["seq"]:03d}' for rid, row in self.rows.items()}
        self.decode = {alias: rid for rid, alias in self.encode.items()}
        self.exact = {(r['kind'], store.ref(rid)['id'], r['version'], r['revision']): rid
                      for rid, r in self.rows.items()}

    def allowed(self, kinds=None):
        return [self.encode[rid] for rid, row in self.rows.items()
                if kinds is None or row['kind'] in kinds]

    def resolve(self, value, kinds=None):
        rid = self.decode.get(value)
        if rid is None or kinds and self.rows[rid]['kind'] not in kinds:
            raise Rejected('UnknownOrWrongSource')
        return rid

    def project(self, value):
        if isinstance(value, dict):
            if {'kind', 'id', 'version', 'revision'} <= value.keys() and set(value) <= {'kind', 'id', 'version', 'revision', 'content_hash'}:
                key = (value['kind'], value['id'], value['version'], value['revision'])
                if key in self.exact:
                    return {'kind': value['kind'], 'id': self.encode[self.exact[key]]}
                # An exact backend link is not another writable model identity.
                return {'kind': value['kind'], 'binding': 'backend-only, not selectable'}
            projected = {key: (bool(item) if key == 'correction_of' else self.project(item)) for key, item in value.items()
                         if key not in ('object_id', 'version', 'revision', 'standing', 'dispatch', 'payload_hash')}
            if value.get('kind') == 'Observation' and 'body' in projected:
                body = projected['body']
                if 'current_purpose' in body:
                    body['activity_at_observation'] = body.pop('current_purpose')
            return projected
        if isinstance(value, list):
            return [self.project(item) for item in value]
        if isinstance(value, str):
            return self.encode.get(value, value)
        return value

    def schema(self, purpose, original):
        schema = deepcopy(original)
        def scalar(kinds=None):
            values = self.allowed(kinds)
            return {'type': 'string', 'enum': values} if values else {'not': {}}
        def array(kinds=None):
            return {'type': 'array', 'items': scalar(kinds), 'uniqueItems': True}
        props = schema['properties']
        if purpose == 'Observation':
            # Runtime state is bound by the owner; it is not a semantic prediction.
            props.pop('current_purpose')
            schema['required'].remove('current_purpose')
            props['source_ids'] = array(['Event'])
            props['work_steps']['items']['properties']['source_id'] = scalar(['Event'])
        elif purpose == 'Policy':
            props['source_ids'] = array()
            props['action_type']['enum'] = [*self.semantic['admissible_actions'], 'None']
        elif purpose in ('Evidence', 'Belief'):
            item = props['items']['items']['properties']
            item['claim_id'] = scalar(['Claim'])
            if purpose == 'Evidence':
                for field, kind in [('source_ids', 'Event'), ('observation_ids', 'Observation'),
                                    ('assistance_ids', 'ActionOccurrence')]:
                    item[field] = array([kind])
            else:
                item['evidence_ids'] = array(['Evidence'])
                item['conflicts']['items']['properties']['evidence_ids'] = array(['Evidence'])
        elif purpose == 'Review':
            check = props['checks']['items']
            check['properties']['source_ids'] = array()
            # The caller binds the four rule names for the stage being reviewed.
        return schema

    def manifest(self):
        return {alias: self.store.ref(rid) for alias, rid in self.decode.items()}
