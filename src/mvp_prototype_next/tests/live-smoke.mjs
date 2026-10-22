// Explicit provider calls: one lecture, or --check for a question followed by help.
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createPrototypeServer } from '../scripts/serve.mjs';
import { loadConfig } from '../scripts/config.mjs';

const directory = fileURLToPath(new URL(`../../../.tmp/mvp-prototype-next/verification/${Date.now()}/`,import.meta.url));
await mkdir(directory,{recursive:true});
const config = await loadConfig();
assert.ok(config.key,'Missing server-side model configuration');
const server = createPrototypeServer({config,directory});
server.listen(0,'127.0.0.1'); await once(server,'listening');
const base = `http://127.0.0.1:${server.address().port}`;
const post = async (url,body) => {
  const response = await fetch(base+url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  assert.equal(response.status,200); return response.json();
};
async function settle(endpoint) {
  let result; const started = Date.now();
  do { await new Promise(r=>setTimeout(r,700)); result = await (await fetch(base+endpoint)).json(); }
  while(result.pending && Date.now()-started < 105000);
  assert.equal(result.pending,null); assert.equal(result.error,null,JSON.stringify(result.error));
  return result;
}
try {
  const s = await post('/api/live/sessions',{space:'math-6b',creationId:crypto.randomUUID()});
  const endpoint = `/api/live/sessions/${s.id}`;
  const check = process.argv.includes('--check');
  const start = Date.now();
  await post(endpoint+'/commands',{requestId:crypto.randomUUID(),kind:check ? 'check_request' : 'message',
    ...(!check ? {text:'请用一个六年级能理解的例子解释正比例和反比例的区别。这轮只讲解，不出检测题。'} : {}),context:{page:'textbook',label:'教材'}});
  let result = await settle(endpoint);
  assert.equal(result.turns.length,2);
  if (check) {
    const q = result.turns[1].blocks.find(b=>b.type==='question');
    assert.equal(q.mode,'check'); assert.equal(q.state,'offered'); assert.ok(!('referenceAnswer' in q));
    await post(endpoint+'/commands',{requestId:crypto.randomUUID(),kind:'start_check',questionId:q.id});
    const helped = await post(endpoint+'/commands',{requestId:crypto.randomUUID(),kind:'help',questionId:q.id,text:'我还没有提交答案，请先讲思路。'});
    assert.equal(helped.check,null); assert.equal(helped.turns[1].blocks.find(b=>b.id===q.id).state,'helped');
    result = await settle(endpoint); assert.equal(result.turns.length,4);
    assert.equal(result.turns[1].blocks.find(b=>b.id===q.id).answer,undefined);
  }
  const reply = result.turns[1];
  assert.ok(reply.blocks.length>0);
  assert.ok(!JSON.stringify(result).includes('referenceAnswer'));
  const report = {checkedAt:new Date().toISOString(),scenario:check ? 'question-help' : 'lecture',model:config.model,scope:result.scope,elapsedMs:Date.now()-start,
    activity:reply.activity,blocks:reply.blocks,turns:result.turns,calls:result.turns.flatMap(t=>t.metrics?.calls || []),passed:true};
  await writeFile(path.join(directory,'report.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({passed:true,model:config.model,elapsedMs:report.elapsedMs,activity:reply.activity,
    blockTypes:reply.blocks.map(b=>b.type),calls:report.calls.length,report:path.join(directory,'report.json')}));
} finally { await new Promise(r=>server.close(r)); }
