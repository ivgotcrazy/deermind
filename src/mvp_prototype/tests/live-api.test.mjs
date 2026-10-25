import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { once } from 'node:events';
import { createPrototypeServer } from '../scripts/serve.mjs';

test('HTTP scope, private fields, persistence and same-origin boundary', async t => {
  const directory = await mkdtemp(path.join(tmpdir(),'deermind-next-api-'));
  let calls = 0, context;
  const server = createPrototypeServer({directory,config:{key:'test',model:'fixed'},provider:async messages => {
    calls++; context = messages;
    return {raw:JSON.stringify({blocks:[{type:'question',mode:'practice',prompt:'2 + 3 = ?',referenceAnswer:'private-five'}],suggestions:[]})};
  }});
  server.listen(0,'127.0.0.1'); await once(server,'listening');
  t.after(async () => {await new Promise(resolve => server.close(resolve)); await rm(directory,{recursive:true,force:true});});
  const base = `http://127.0.0.1:${server.address().port}`;
  const post = (url, body) => fetch(base + url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const status = await (await fetch(base+'/api/live/status')).json();
  assert.equal(status.configured,true); assert.ok(!('key' in status));
  assert.equal((await fetch(base+'/api/live/status',{headers:{Origin:'https://example.com'}})).status,403);
  assert.equal((await fetch(base+'/.env')).status,404);
  assert.equal((await post('/api/live/sessions',{space:'chinese-6b',creationId:'test-chinese'})).status,400);
  const created = await (await post('/api/live/sessions',{space:'math-6b',creationId:'test-create',scope:{label:'六上'},mastery:99})).json();
  assert.equal(created.scope.label,'六年级下册数学'); assert.ok(!JSON.stringify(created).includes('99'));
  const endpoint = `/api/live/sessions/${created.id}`;
  const cmd = {requestId:'request-001',kind:'message',text:'给我一道练习',context:{page:'textbook',label:'教材',mastery:99}};
  assert.equal((await post(endpoint+'/commands',cmd)).status,200);
  let result;
  for(let n=0;n<100;n++) {result = await (await fetch(base+endpoint)).json(); if(!result.pending) break; await new Promise(r=>setTimeout(r,10));}
  assert.equal(result.error,null); assert.equal(result.turns.length,2);
  assert.ok(!JSON.stringify(result).includes('private-five'));
  assert.ok((await readFile(path.join(directory,`${created.id}.json`),'utf8')).includes('private-five'));
  assert.ok(!JSON.stringify(context).includes('"mastery"'));
  await post(endpoint+'/commands',cmd); assert.equal(calls,1);
  assert.equal((await post(endpoint+'/commands',{...cmd,text:'different'})).status,409);
  await writeFile(path.join(directory,'NEXT-corrupted.json'),'broken');
  assert.equal((await post('/api/live/sessions',{space:'math-6b',creationId:'corrupted'})).status,409);
  assert.equal(await readFile(path.join(directory,'NEXT-corrupted.json'),'utf8'),'broken');
});
