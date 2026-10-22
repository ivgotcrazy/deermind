import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { once } from 'node:events';
import { createPrototypeServer } from '../scripts/serve.mjs';

test('admin inspection is read-only, scope-bound and exposes unreadable files without private answer fields',async t=>{
  const directory=await mkdtemp(path.join(tmpdir(),'deermind-admin-read-'));
  let calls=0;
  const server=createPrototypeServer({directory,config:{key:'fixed',model:'fixed-model'},provider:async()=>{calls++;throw Error('Must not invoke');}});
  server.listen(0,'127.0.0.1');await once(server,'listening');
  t.after(async()=>{await new Promise(r=>server.close(r));await rm(directory,{recursive:true,force:true});});
  const base=`http://127.0.0.1:${server.address().port}`;
  const fixture={version:2,revision:7,id:'NEXT-review-001',scope:{space:'math-6b',label:'六下'},model:'fixed',phase:'learning',pending:{id:'previous-pending',startedAt:'2026-10-20T00:00:00Z'},error:null,turns:[{id:'t1',role:'assistant',blocks:[{type:'question',prompt:'测试题',referenceAnswer:'PRIVATE-ANSWER'}],raw:'PRIVATE-RAW'}],createdAt:'2026-10-20',updatedAt:'2026-10-20',requests:{secret:'fingerprint'},lastCommand:{kind:'message'}};
  const file=path.join(directory,fixture.id+'.json');await writeFile(file,JSON.stringify(fixture));
  await writeFile(path.join(directory,'NEXT-other-001.json'),JSON.stringify({...fixture,id:'NEXT-other-001',scope:{space:'other',label:'other'}}));
  await writeFile(path.join(directory,'NEXT-bad-001.json'),'broken');
  const before=await readFile(file,'utf8');
  const index=await(await fetch(base+'/api/live/admin/sessions')).json();
  assert.equal(index.items.length,1);assert.equal(index.unreadable.length,1);assert.equal(index.items[0].pending,true);
  const detail=await(await fetch(base+'/api/live/admin/sessions/'+fixture.id)).json();
  assert.equal(detail.revision,7);assert.equal(detail.pending.id,'previous-pending');assert.ok(!JSON.stringify(detail).includes('PRIVATE'));assert.ok(!('requests'in detail));
  assert.equal(await readFile(file,'utf8'),before);assert.equal(calls,0);
  assert.equal((await fetch(base+'/api/live/admin/sessions/NEXT-other-001')).status,409);
  assert.equal((await fetch(base+'/api/live/admin/sessions/NEXT-bad-001')).status,409);
  assert.equal((await fetch(base+'/api/live/admin/sessions',{headers:{Origin:'https://untrusted.example'}})).status,403);
});
