"""SQLite authority, immutable records, exact dependencies and durable session state."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
import threading
import time

from .common import OWNERS, Rejected, digest, dumps, now, uid
from .contracts import validate, NORM, PACKAGE
from .domain import definitions
from .protocols import RULES

DDL = """
CREATE TABLE IF NOT EXISTS records(
 id TEXT PRIMARY KEY,kind TEXT NOT NULL,obj TEXT NOT NULL,revision INTEGER NOT NULL,version TEXT NOT NULL,
 owner TEXT NOT NULL,sid TEXT NOT NULL,turn_id TEXT NOT NULL,body TEXT NOT NULL,hash TEXT NOT NULL,created TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS immutable_update BEFORE UPDATE ON records BEGIN SELECT RAISE(ABORT,'ImmutableRecord'); END;
CREATE TRIGGER IF NOT EXISTS immutable_delete BEFORE DELETE ON records BEGIN SELECT RAISE(ABORT,'ImmutableRecord'); END;
CREATE TABLE IF NOT EXISTS validity(rid TEXT PRIMARY KEY REFERENCES records(id),valid INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS heads(obj TEXT PRIMARY KEY,rid TEXT NOT NULL REFERENCES records(id));
CREATE TABLE IF NOT EXISTS deps(child TEXT REFERENCES records(id),parent TEXT REFERENCES records(id),mode TEXT NOT NULL,use TEXT NOT NULL,PRIMARY KEY(child,parent,mode,use));
CREATE INDEX IF NOT EXISTS deps_parent ON deps(parent);
CREATE INDEX IF NOT EXISTS records_session ON records(sid,kind);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,subject TEXT NOT NULL,purpose TEXT NOT NULL,activity_rev INTEGER NOT NULL,
 auth_rev INTEGER NOT NULL,authorized INTEGER NOT NULL,epoch INTEGER NOT NULL,isolated INTEGER NOT NULL,active_turn TEXT);
CREATE TABLE IF NOT EXISTS turns(id TEXT PRIMARY KEY,sid TEXT REFERENCES sessions(id),message_key TEXT NOT NULL,event_id TEXT REFERENCES records(id),
 status TEXT NOT NULL,phase TEXT NOT NULL,generation INTEGER NOT NULL,worker_epoch INTEGER NOT NULL,error TEXT NOT NULL,created REAL NOT NULL,UNIQUE(sid,message_key));
CREATE TABLE IF NOT EXISTS intents(id TEXT PRIMARY KEY REFERENCES records(id),sid TEXT NOT NULL,turn_id TEXT NOT NULL,
 dispatch TEXT UNIQUE NOT NULL,status TEXT NOT NULL,epoch INTEGER NOT NULL,expires REAL NOT NULL,payload TEXT NOT NULL,
 payload_hash TEXT NOT NULL,rendered TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,source TEXT NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recompute_requests(turn_id TEXT PRIMARY KEY REFERENCES turns(id),target_observation TEXT NOT NULL REFERENCES records(id),reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
"""


class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.db=sqlite3.connect(str(path),check_same_thread=False,isolation_level=None,timeout=10)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript(DDL)
        assert self.db.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert self.db.execute('PRAGMA synchronous').fetchone()[0]==2

    @contextmanager
    def tx(self):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:yield self.db;self.db.execute('COMMIT')
            except BaseException:self.db.execute('ROLLBACK');raise

    def _row(self,rid):
        r=self.db.execute('SELECT rowid AS seq,* FROM records WHERE id=?',(rid,)).fetchone()
        if not r:raise Rejected('MissingSource:'+rid)
        return {**dict(r),'body':json.loads(r['body'])}

    def get(self,rid):
        with self.lock:return self._row(rid)

    def ref(self,rid):
        r=self._row(rid)
        ident=r['obj'].split(':',2)[2] if r['version'] else r['obj'] if r['revision'] else r['id']
        return {'kind':r['kind'],'id':ident,'version':r['version'],'revision':r['revision'],'content_hash':r['hash']}

    def resolve(self,ref):
        if ref['version']:rid=f"{ref['kind']}:{ref['id']}:{ref['version']}"
        elif ref['revision']:
            row=self.db.execute('SELECT id FROM records WHERE kind=? AND obj=? AND revision=?',(ref['kind'],ref['id'],ref['revision'])).fetchone()
            if not row:raise Rejected('MissingExactRevision')
            rid=row[0]
        else:rid=ref['id']
        r=self._row(rid)
        if self.ref(rid)!=ref:raise Rejected('ReferenceHashMismatch')
        return r

    def _insert(self,kind,body,owner='Runtime',sid='',turn='',obj=None,revision=0,version='',rid=None,dependencies=()):
        rid=rid or uid(kind.lower());obj=obj or rid
        self.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?)',
          (rid,kind,obj,revision,version,owner,sid,turn,dumps(body),digest(body),now()))
        self.db.execute('INSERT INTO validity VALUES(?,1)',(rid,))
        for parent,mode,use in dependencies:self.db.execute('INSERT INTO deps VALUES(?,?,?,?)',(rid,parent,mode,use))
        return rid

    def record(self,kind,body,owner='Runtime',sid='',turn='',dependencies=()):
        with self.tx():return self._insert(kind,body,owner,sid,turn,dependencies=dependencies)

    def current(self,rid):
        r=self._row(rid)
        v=self.db.execute('SELECT valid FROM validity WHERE rid=?',(rid,)).fetchone()
        if not v['valid']:return False
        h=self.db.execute('SELECT rid FROM heads WHERE obj=?',(r['obj'],)).fetchone()
        return h is None or h['rid']==rid

    def head(self,obj,required=True):
        with self.lock:
            h=self.db.execute('SELECT rid FROM heads WHERE obj=?',(obj,)).fetchone()
            if h and self.current(h['rid']):return self._row(h['rid'])
            if required:raise Rejected('NoCurrentValidState:'+obj)
            return None

    def rows(self,kind=None,sid=None,current=False):
        with self.lock:
            args=[];where=[]
            if kind:where.append('kind=?');args.append(kind)
            if sid is not None:where.append('sid=?');args.append(sid)
            sql='SELECT id FROM records'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY rowid'
            return [self._row(r[0]) for r in self.db.execute(sql,args).fetchall() if not current or self.current(r[0])]

    def _invalidate(self,rid,include=True):
        ids=[r[0] for r in self.db.execute("WITH RECURSIVE affected(id) AS (SELECT ? UNION SELECT d.child FROM deps d JOIN affected a ON d.parent=a.id WHERE d.mode='CURRENT') SELECT id FROM affected",(rid,)).fetchall()]
        if not include:ids=[x for x in ids if x!=rid]
        for i in ids:
            self.db.execute('UPDATE validity SET valid=0 WHERE rid=?',(i,))
            self.db.execute('INSERT INTO jobs VALUES(?,?,?,?)',(uid('job'),i,'PENDING',now()))
        return ids

    def invalidate(self,rid,actor):
        if actor!='admin':raise Rejected('Unauthorized')
        with self.tx():
            affected=self._invalidate(rid)
            self._insert('Correction',{'target':self.ref(rid),'affected':affected},'Governance')
            return affected

    def canonical(self,proposal,actor='admin',activate=True):
        if actor!='admin':raise Rejected('Unauthorized')
        kind,ident,version,body=(proposal[k] for k in ('kind','id','version','body'))
        if kind in NORM:validate(NORM[kind],body)
        owner=OWNERS[kind];obj=f'canonical:{kind}:{ident}';rid=f'{kind}:{ident}:{version}'
        with self.tx():
            found=self.db.execute('SELECT hash FROM records WHERE id=?',(rid,)).fetchone()
            if found:
                if found[0]!=digest(body):raise Rejected('CanonicalVersionConflict')
                return rid
            prior=self.db.execute('SELECT rid FROM heads WHERE obj=?',(obj,)).fetchone()
            proposal_id=self._insert('ChangeProposal',{'kind':kind,'id':ident,'version':version,'body_hash':digest(body),'base':prior[0] if prior else None},owner)
            decision=self._insert('GovernanceDecision',{'proposal':proposal_id,'body_hash':digest(body),'scope':obj,'authorized_actor':actor,'decision':'APPROVE'},'Governance')
            self._insert(kind,body,owner,obj=obj,version=version,rid=rid,dependencies=[(decision,'PINNED','governance')])
            if activate:self._activate(rid,actor)
        return rid

    def _activate(self,rid,actor):
        if actor!='admin':raise Rejected('Unauthorized')
        r=self._row(rid)
        if not r['version']:raise Rejected('NotCanonical')
        prior=self.db.execute('SELECT rid FROM heads WHERE obj=?',(r['obj'],)).fetchone()
        if prior and prior[0]!=rid:self._invalidate(prior[0],False)
        self.db.execute('INSERT INTO heads VALUES(?,?) ON CONFLICT(obj) DO UPDATE SET rid=excluded.rid',(r['obj'],rid))
        self._insert('ActivationRecord',{'version_ref':self.ref(rid),'previous':prior[0] if prior else None,'actor':actor},'Governance')

    def activate(self,rid,actor):
        with self.tx():self._activate(rid,actor)

    def bootstrap(self):
        if not self.rows('TaskFamily'):
            for p in definitions():self.canonical(p)

    def start_session(self,sid,subject='synthetic-learner'):
        with self.tx():
            self.db.execute("INSERT OR IGNORE INTO sessions VALUES(?,?,'IndependentDiagnosis',0,0,1,1,0,NULL)",(sid,subject))
        return self.session(sid)

    def session(self,sid):
        with self.lock:
            r=self.db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
            if not r:raise Rejected('UnknownSession')
            return dict(r)

    def turn(self,tid):
        with self.lock:
            r=self.db.execute('SELECT * FROM turns WHERE id=?',(tid,)).fetchone()
            if not r:raise Rejected('UnknownTurn')
            return dict(r)

    def enqueue(self,sid,key,text,task_ref,actor='learner',correction_of=None):
        if actor!='learner':raise Rejected('Unauthorized')
        with self.tx():
            self.session(sid)
            old=self.db.execute('SELECT id FROM turns WHERE sid=? AND message_key=?',(sid,key)).fetchone()
            if old:return self.turn(old[0])
            self._row(task_ref)
            tid=uid('turn')
            event=self._insert('Event',{'type':'LearnerInput','text':text,'task_ref':self.ref(task_ref),'correction_of':correction_of},'Learner',sid,tid)
            if correction_of:
                target=self._row(correction_of)
                if target['sid']!=sid or target['kind']!='Observation':raise Rejected('UnauthorizedCorrection')
                self._invalidate(correction_of)
            self.db.execute("INSERT INTO turns VALUES(?,?,?,?,'QUEUED','RECEIVED',0,0,'',?)",(tid,sid,key,event,time.time()))
            return self.turn(tid)

    def claim_turn(self,worker_epoch):
        with self.tx():
            row=self.db.execute("SELECT t.* FROM turns t JOIN sessions s ON s.id=t.sid WHERE t.status='QUEUED' AND s.active_turn IS NULL AND s.isolated=0 ORDER BY t.created LIMIT 1").fetchone()
            if not row:return None
            self.db.execute("UPDATE turns SET status='RUNNING',worker_epoch=? WHERE id=?",(worker_epoch,row['id']))
            self.db.execute('UPDATE sessions SET active_turn=? WHERE id=?',(row['id'],row['sid']))
            return self.turn(row['id'])

    def request_recompute(self,observation_id,reason,actor):
        if actor!='admin':raise Rejected('Unauthorized')
        with self.tx():
            observation=self._row(observation_id)
            if observation['kind']!='Observation':raise Rejected('InvalidRecomputeTarget')
            oldturn=self.turn(observation['turn_id']);tid=uid('turn');sid=observation['sid']
            self._invalidate(observation_id)
            self.db.execute("INSERT INTO turns VALUES(?,?,?,?,'QUEUED','RECEIVED',0,0,'',?)",(tid,sid,uid('recompute'),oldturn['event_id'],time.time()))
            self.db.execute('INSERT INTO recompute_requests VALUES(?,?,?)',(tid,observation_id,reason))
            self._insert('RecomputeRequested',{'target_ref':self.ref(observation_id),'original_event_id':oldturn['event_id'],'reason':reason},'Governance',sid,tid)
            return self.turn(tid)

    def recover(self):
        with self.tx():
            row=self.db.execute("SELECT value FROM meta WHERE key='worker_epoch'").fetchone();epoch=int(row[0])+1 if row else 1
            self.db.execute("INSERT INTO meta VALUES('worker_epoch',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(epoch),))
            for t in self.db.execute("SELECT * FROM turns WHERE status IN ('RUNNING','WAITING_EFFECT')").fetchall():
                intents=self.db.execute('SELECT * FROM intents WHERE turn_id=?',(t['id'],)).fetchall()
                unknown=any(i['status'] in ('DISPATCHED','INDETERMINATE') for i in intents)
                pending=any(i['status']=='PENDING' for i in intents)
                if unknown:
                    self.db.execute("UPDATE intents SET status='INDETERMINATE' WHERE turn_id=? AND status='DISPATCHED'",(t['id'],))
                    self.db.execute('UPDATE sessions SET isolated=1 WHERE id=?',(t['sid'],))
                elif not pending:
                    self.db.execute("UPDATE turns SET status='FAILED',error='ProcessInterrupted',generation=generation+1 WHERE id=?",(t['id'],))
                    self.db.execute('UPDATE sessions SET active_turn=NULL WHERE id=?',(t['sid'],))
                self._insert('RecoveryRecord',{'turn_id':t['id'],'unknown_effect':unknown,'pending_intent':pending,'worker_epoch':epoch},sid=t['sid'],turn=t['id'])
            return epoch

    def checkpoint(self,tid,phase):
        with self.tx():self.db.execute('UPDATE turns SET phase=? WHERE id=?',(phase,tid))

    def finish(self,tid,error=''):
        with self.tx():
            t=self.turn(tid)
            # A late worker return cannot overwrite an already terminal cancellation.
            if t['status'] in ('COMPLETED','FAILED'):return
            error=t['error'] or error
            in_flight=self.db.execute("SELECT id FROM intents WHERE turn_id=? AND status IN ('DISPATCHED','INDETERMINATE')",(tid,)).fetchall()
            if in_flight:
                self.db.execute('UPDATE sessions SET isolated=1 WHERE id=?',(t['sid'],))
                self.db.execute("UPDATE turns SET status='WAITING_EFFECT',error=? WHERE id=?",(error,tid))
                return
            self.db.execute("UPDATE turns SET status=?,error=?,generation=generation+1 WHERE id=?",('FAILED' if error else 'COMPLETED',error,tid))
            self.db.execute('UPDATE sessions SET active_turn=NULL WHERE id=? AND active_turn=?',(t['sid'],tid))

    def interrupt(self,sid):
        with self.tx():
            s=self.session(sid);tid=s['active_turn']
            if not tid:return
            self.db.execute("UPDATE turns SET generation=generation+1,error='UserInterrupted' WHERE id=?",(tid,))
            for i in self.db.execute("SELECT id FROM intents WHERE turn_id=? AND status='PENDING'",(tid,)).fetchall():self._not_occurred(i[0],'UserInterrupted')
        self.finish(tid,'UserInterrupted')

    def authorize(self,sid,allowed,actor):
        if actor!='admin':raise Rejected('Unauthorized')
        with self.tx():
            self.db.execute('UPDATE sessions SET authorized=?,auth_rev=auth_rev+1 WHERE id=?',(int(allowed),sid))
            self._insert('AuthorityChanged',{'authorized':bool(allowed)},'Governance',sid)

    def make_context(self,sid,tid,purpose,semantic,refs,expected_heads):
        with self.tx():
            s=self.session(sid);t=self.turn(tid)
            if t['status']!='RUNNING' or t['error']:raise Rejected('TurnRetired')
            control={'sid':sid,'turn_id':tid,'purpose':purpose,'auth_rev':s['auth_rev'],'activity_rev':s['activity_rev'],
              'generation':t['generation'],'worker_epoch':t['worker_epoch'],'expected_heads':expected_heads,'refs':refs}
            return self._insert('Context',{'semantic':semantic,'control':control},sid=sid,turn=tid,dependencies=[(rid,'PINNED','assembled material') for rid in refs])

    def _check_context(self,context):
        c=context['body']['control'];s=self.session(c['sid']);t=self.turn(c['turn_id'])
        epoch=int(self.db.execute("SELECT value FROM meta WHERE key='worker_epoch'").fetchone()[0])
        if t['status']!='RUNNING' or t['error'] or t['generation']!=c['generation'] or epoch!=c['worker_epoch']:raise Rejected('TurnRetired')
        if not s['authorized']:raise Rejected('Unauthorized')
        if s['auth_rev']!=c['auth_rev'] or s['activity_rev']!=c['activity_rev']:raise Rejected('CandidateStale')
        for obj,rid in c['expected_heads'].items():
            row=self.head(obj,False)
            if (row['id'] if row else None)!=rid:raise Rejected('CandidateStale')
        for rid in c['refs']:
            if not self.current(rid):raise Rejected('DependencyInvalid')

    def commit(self,kind,owner,context_id,candidate_id,review_id,items):
        """items = (object identity, formal body, exact dependency triples)."""
        if OWNERS.get(kind)!=owner:raise Rejected('WrongOwner')
        with self.tx():
            ctx=self._row(context_id);candidate=self._row(candidate_id);review=self._row(review_id)
            if candidate['body'].get('context_id')!=context_id or candidate['body'].get('target_kind')!=kind:raise Rejected('CandidateBindingMismatch')
            rb=review['body']
            if rb.get('candidate_id')!=candidate_id or rb.get('candidate_hash')!=candidate['hash'] or rb.get('context_id')!=context_id:raise Rejected('ReviewBindingMismatch')
            if rb.get('verdict')!='PASS' or not rb.get('required_checks_complete'):raise Rejected('RequiredValidationNotPassed')
            purpose='Policy' if kind=='Decision' else kind
            if rb.get('rule_hash')!=digest(RULES[purpose]):raise Rejected('ValidationRuleMismatch')
            if digest([body for _,body,_ in items])!=candidate['body'].get('formal_payload_hash'):raise Rejected('CandidatePayloadMismatch')
            if not self.session(ctx['sid'])['authorized']:raise Rejected('Unauthorized')
            for committed in self.rows('CommitRecord',ctx['sid']):
                if committed['body']['candidate']==candidate_id:return committed['body']['outputs']
            self._check_context(ctx)
            out=[];sid=ctx['sid'];tid=ctx['turn_id']
            for obj,body,deps in items:
                prior=self.db.execute('SELECT rid FROM heads WHERE obj=?',(obj,)).fetchone()
                rev=self._row(prior[0])['revision']+1 if prior else 1
                if prior:self._invalidate(prior[0])
                rid=self._insert(kind,body,owner,sid,tid,obj,rev,dependencies=deps+[(candidate_id,'PINNED','candidate'),(review_id,'PINNED','validation'),(context_id,'PINNED','context')])
                self.db.execute('INSERT INTO heads VALUES(?,?) ON CONFLICT(obj) DO UPDATE SET rid=excluded.rid',(obj,rid));out.append(rid)
                if prior:self.db.execute("UPDATE jobs SET status='REPLACED' WHERE source=? AND status='PENDING'",(prior[0],))
            self._insert('CommitRecord',{'candidate':candidate_id,'review':review_id,'outputs':out,'owner':owner},owner,sid,tid)
            return out

    def create_intent(self,decision_id):
        with self.tx():
            d=self._row(decision_id);p=d['body'];sid=d['sid'];tid=d['turn_id'];s=self.session(sid)
            old=self.db.execute('SELECT id FROM records WHERE kind=? AND obj=?',('ActionIntent','intent:'+decision_id)).fetchone()
            if old:return old[0]
            if not self.current(decision_id) or not s['authorized']:raise Rejected('InvalidDecision')
            rid=self._insert('ActionIntent',{'decision_ref':self.ref(decision_id),'action_type':p['action_type'],'blocks':p['blocks'],'transition':p['transition'],
                   'auth_rev':s['auth_rev'],'activity_rev':s['activity_rev']},'Interaction',sid,tid,'intent:'+decision_id,1,dependencies=[(decision_id,'CURRENT','approved decision')])
            payload={'action_type':p['action_type'],'blocks':p['blocks'],'transition':p['transition']}
            self.db.execute("INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)",(rid,sid,tid,uid('dispatch'),'PENDING',s['epoch'],time.time()+60,dumps(payload),digest(payload),'[]',time.time()))
            return rid

    def _not_occurred(self,iid,reason):
        i=self.db.execute('SELECT * FROM intents WHERE id=?',(iid,)).fetchone()
        self.db.execute("UPDATE intents SET status='NOT_OCCURRED' WHERE id=?",(iid,))
        self._insert('NotOccurred',{'intent_ref':self.ref(iid),'dispatch':i['dispatch'],'reason':reason},'Interaction',i['sid'],i['turn_id'],dependencies=[(iid,'PINNED','intent')])

    def dispatch(self,sid,epoch):
        with self.tx():
            s=self.session(sid)
            if s['isolated'] or s['epoch']!=epoch:return None
            i=self.db.execute("SELECT * FROM intents WHERE sid=? AND status='PENDING' ORDER BY created LIMIT 1",(sid,)).fetchone()
            if not i:return None
            intent=self._row(i['id']);t=self.turn(i['turn_id'])
            if (not s['authorized'] or not self.current(i['id']) or i['expires']<time.time() or t['error'] or
                intent['body']['auth_rev']!=s['auth_rev'] or intent['body']['activity_rev']!=s['activity_rev']):
                self._not_occurred(i['id'],'PreconditionInvalidated');return None
            payload=json.loads(i['payload'])
            if payload['action_type']=='Control':
                self.db.execute("UPDATE sessions SET purpose='Teaching',activity_rev=activity_rev+1 WHERE id=?",(sid,))
                self.db.execute("UPDATE intents SET status='OCCURRED' WHERE id=?",(i['id'],))
                self._insert('ActivityTransitionOccurred',{'intent_ref':self.ref(i['id']),'transition':'Teaching'},'Interaction',sid,i['turn_id'],dependencies=[(i['id'],'PINNED','intent')])
                return {'control_completed':True}
            self.db.execute("UPDATE intents SET status='DISPATCHED' WHERE id=?",(i['id'],))
            self._insert('DispatchRecord',{'intent_ref':self.ref(i['id']),'dispatch':i['dispatch'],'epoch':epoch,'payload_hash':i['payload_hash']},'Interaction',sid,i['turn_id'])
            return {'intent_id':i['id'],'dispatch_id':i['dispatch'],'epoch':epoch,'payload_hash':i['payload_hash'],'payload':payload}

    def acknowledge(self,sid,dispatch_id,epoch,payload_hash,rendered):
        with self.tx():
            i=self.db.execute('SELECT * FROM intents WHERE dispatch=? AND sid=?',(dispatch_id,sid)).fetchone()
            if not i or epoch!=i['epoch'] or payload_hash!=i['payload_hash']:raise Rejected('EffectBindingMismatch')
            s=self.session(sid)
            if epoch!=s['epoch']:raise Rejected('RetiredChannel')
            payload=json.loads(i['payload']);byid={b['block_id']:b for b in payload['blocks']}
            if len(rendered)!=len(set(rendered)) or any(x not in byid for x in rendered):raise Rejected('InvalidRenderedSubset')
            if rendered!=[b['block_id'] for b in payload['blocks'] if b['block_id'] in rendered]:raise Rejected('InvalidRenderedOrder')
            if i['status']=='OCCURRED':
                if json.loads(i['rendered'])!=rendered:raise Rejected('ConflictingEffectConfirmation')
                return 'DUPLICATE'
            if i['status'] not in ('DISPATCHED','INDETERMINATE'):raise Rejected('NotDispatched')
            actual=[byid[k] for k in rendered]
            self._insert('ActionOccurrence',{'intent_ref':self.ref(i['id']),'dispatch':dispatch_id,'payload_hash':payload_hash,'blocks':actual,
                'completeness':'FULL' if len(actual)==len(payload['blocks']) else 'PARTIAL','boundary':'client-confirmed-render','epoch':epoch},'Interaction',sid,i['turn_id'],dependencies=[(i['id'],'PINNED','intent')])
            self.db.execute("UPDATE intents SET status='OCCURRED',rendered=? WHERE id=?",(dumps(rendered),i['id']))
            return 'RECORDED'

    def isolate(self,iid):
        with self.tx():
            i=self.db.execute('SELECT * FROM intents WHERE id=?',(iid,)).fetchone()
            if i['status']=='DISPATCHED':
                self.db.execute("UPDATE intents SET status='INDETERMINATE' WHERE id=?",(iid,))
                self.db.execute('UPDATE sessions SET isolated=1 WHERE id=?',(i['sid'],))
                self._insert('EffectIndeterminate',{'intent_ref':self.ref(iid),'dispatch':i['dispatch']},'Interaction',i['sid'],i['turn_id'])

    def stop_channel(self,sid,epoch):
        with self.tx():
            s=self.session(sid)
            if epoch!=s['epoch']:raise Rejected('RetiredChannel')
            self._insert('ChannelStopped',{'epoch':epoch,'basis':'controlled client stopped and reconciled rendered blocks'},'Interaction',sid)
            self.db.execute("UPDATE intents SET status='ISOLATED_UNKNOWN' WHERE sid=? AND status IN ('DISPATCHED','INDETERMINATE')",(sid,))
            self.db.execute('UPDATE sessions SET epoch=epoch+1,isolated=0 WHERE id=?',(sid,))
            tid=s['active_turn']
        if tid:self.finish(tid,self.turn(tid)['error'] or 'UnknownEffectIsolated')
        return self.session(sid)['epoch']

    def intent(self,iid):
        with self.lock:
            i=self.db.execute('SELECT * FROM intents WHERE id=?',(iid,)).fetchone()
            return dict(i) if i else None

    def reconstruct(self,rid,actor,missing=()):
        if actor!='admin':raise Rejected('UnauthorizedHistoricalRead')
        with self.lock:
            seen=set();pending=[rid];records=[];absent=[]
            while pending:
                key=pending.pop()
                if key in seen:continue
                seen.add(key)
                if key in missing:absent.append(key);continue
                try:records.append(self._row(key))
                except Rejected:absent.append(key);continue
                pending.extend(r[0] for r in self.db.execute('SELECT parent FROM deps WHERE child=?',(key,)))
            return {'status':('UNAVAILABLE' if not records else 'PARTIAL') if absent else 'FULL','records':records,'missing':absent}
