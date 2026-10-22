import assert from 'node:assert/strict';
import { mkdtemp, rm, mkdir, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const directory = await mkdtemp(path.join(tmpdir(),'deermind-next-controls-'));
const screenshots = fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/',import.meta.url));
await mkdir(screenshots,{recursive:true});
const reply = text => ({raw:JSON.stringify({blocks:[{type:'text',text}],suggestions:[]})});
const question = mode => ({raw:JSON.stringify({activity:{mode:'error-check',phase:'practice',title:'比例检测'},
  blocks:[{type:'question',mode,prompt:'同样的笔，3 支共 6 元。5 支共多少元？',referenceAnswer:'PRIVATE-REFERENCE: 10 元'}],suggestions:[]})});
let calls = 0, behavior = async () => question('check'), releaseLate;
const server = createPrototypeServer({directory,config:{key:'fixture',model:'fixed'},provider:async () => {
  calls++; return behavior();
}});
server.listen(0,'127.0.0.1'); await once(server,'listening');
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
const page = await browser.newPage({viewport:{width:1360,height:900}});
const errors = [];
page.on('pageerror',e=>errors.push(e.message));
const stored = () => page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-next-workspace-v1')));
const session = async () => (await fetch(`${base}/api/live/sessions/${(await stored()).sessionId}`)).json();
const latestQuestion = () => page.locator('.question').last();
const waitReply = () => page.waitForFunction(()=>!document.querySelector('.typing-indicator'));
const send = async text => {
  await page.locator('.input-area').fill(text); await page.locator('.input-composer .send-btn').click();
};
try {
  await page.goto(base+'/student/');
  await page.locator('.nav-item').filter({hasText:'教材'}).click();
  const source = await page.locator('.static-pane').innerText();
  await page.locator('.bottom-input-bar input').fill('给我一道比例检测题');
  await page.locator('.bottom-input-bar .send-btn').click();
  await page.getByRole('button',{name:'开始检测',exact:true}).waitFor();
  assert.equal(calls,1);
  assert.equal(await latestQuestion().locator('textarea').count(),0);
  assert.ok(!(await page.locator('body').innerText()).includes('PRIVATE-REFERENCE'));
  assert.ok(!JSON.stringify(await session()).includes('referenceAnswer'));
  await page.getByRole('button',{name:'开始检测',exact:true}).click();
  await latestQuestion().locator('textarea').fill('答案草稿，尚未提交');
  const id = (await session()).check;
  assert.ok(id); assert.equal(calls,1);
  await page.getByTitle('收起聊天').click(); await page.reload();
  await page.locator('.main-content.collapsed-view').waitFor();
  await page.getByTitle('展开聊天').click();
  await latestQuestion().locator('textarea').waitFor();
  assert.equal(await latestQuestion().locator('textarea').inputValue(),'答案草稿，尚未提交');
  assert.equal((await session()).check,id);
  assert.equal(await page.locator('.input-composer .send-btn').isDisabled(),true);
  await page.screenshot({path:path.join(screenshots,'check-active.png')});
  behavior = async () => {await new Promise(r=>setTimeout(r,150)); return reply('每支 2 元，5 支 10 元。本次计算正确。');};
  await latestQuestion().locator('textarea').fill('每支 2 元，5 支 10 元');
  await page.getByRole('button',{name:'提交答案',exact:true}).evaluate(el=>{el.click();el.click();});
  await page.getByText('每支 2 元，5 支 10 元。本次计算正确。',{exact:true}).waitFor();
  assert.equal(calls,2);
  let record = await session();
  assert.equal(record.check,null); assert.equal(record.turns.filter(t=>t.action==='answer').length,1);
  assert.equal(record.turns[1].blocks[0].state,'answered');
  assert.equal((await stored()).answers[id],undefined);
  assert.equal(await page.locator('.static-pane').innerText(),source);

  behavior = async () => question('practice');
  await send('再给我一道随堂练习');
  await latestQuestion().getByRole('button',{name:'提交答案',exact:true}).waitFor();
  assert.equal(calls,3); assert.equal((await session()).check,null);
  await latestQuestion().locator('textarea').fill('10 元');
  behavior = async () => reply('练习反馈已保留。');
  await latestQuestion().getByRole('button',{name:'提交答案',exact:true}).click();
  await page.getByText('练习反馈已保留。',{exact:true}).waitFor(); assert.equal(calls,4);

  behavior = async () => question('check'); await send('再检测一次');
  await page.getByRole('button',{name:'开始检测',exact:true}).waitFor();
  await page.getByRole('button',{name:'开始检测',exact:true}).click();
  await latestQuestion().locator('textarea').fill('只写在草稿里，不提交给模型');
  const helpId = (await session()).check;
  behavior = async () => {throw Error('simulated transport failure');};
  await page.getByRole('button',{name:'求助',exact:true}).click();
  await page.getByRole('button',{name:'重试',exact:true}).waitFor();
  record = await session(); assert.equal(calls,6);
  assert.equal(record.check,null); assert.equal(record.phase,'learning');
  const helped = record.turns.flatMap(t=>t.blocks||[]).find(b=>b.id===helpId);
  assert.equal(helped.state,'helped'); assert.equal(helped.answer,undefined);
  assert.ok(!JSON.stringify(record).includes('只写在草稿里'));
  assert.equal((await stored()).answers[helpId],'只写在草稿里，不提交给模型');
  behavior = async () => reply('先求一支笔的价格，再计算五支。');
  await page.getByRole('button',{name:'重试',exact:true}).click();
  await page.getByText('先求一支笔的价格，再计算五支。',{exact:true}).waitFor();
  assert.equal(calls,7); assert.equal((await session()).turns.filter(t=>t.action==='help').length,1);
  assert.equal(await page.locator('.static-pane').innerText(),source);
  await page.screenshot({path:path.join(screenshots,'check-help.png')});

  behavior = () => new Promise(r=>releaseLate=r);
  await send('请换一种解释');
  await page.getByRole('button',{name:'停止',exact:true}).waitFor(); assert.equal(calls,8);
  await page.getByTitle('收起聊天').click();
  await page.getByRole('button',{name:'停止',exact:true}).click();
  await page.getByRole('button',{name:'重试',exact:true}).waitFor();
  behavior = async () => reply('重试得到的新讲解。');
  await page.getByRole('button',{name:'重试',exact:true}).click();
  await waitReply(); await page.getByTitle('展开聊天').click();
  await page.getByText('重试得到的新讲解。',{exact:true}).waitFor();
  releaseLate(reply('LATE-REPLY-MUST-NOT-APPEAR'));
  await page.waitForTimeout(150);
  assert.equal(calls,9); record = await session();
  assert.ok(!JSON.stringify(record).includes('LATE-REPLY'));
  assert.equal(record.turns.filter(t=>t.displayText==='请换一种解释').length,1);
  assert.equal(await page.getByRole('button',{name:'停止',exact:true}).count(),0);

  behavior = async () => question('check'); await send('检测提交丢包恢复');
  await page.getByRole('button',{name:'开始检测',exact:true}).waitFor();
  await page.getByRole('button',{name:'开始检测',exact:true}).click();
  await latestQuestion().locator('textarea').fill('10 元，先求单价');
  let dropped = false;
  await page.route('**/commands',async route=>{
    if (!dropped && route.request().postDataJSON()?.kind==='answer') {
      dropped=true; await route.fetch(); await route.abort('failed');
    } else await route.continue();
  });
  behavior = async () => reply('这次答案已收到。');
  await page.getByRole('button',{name:'提交答案',exact:true}).click();
  await page.getByRole('button',{name:'重试',exact:true}).waitFor();
  await page.unroute('**/commands');
  await page.getByRole('button',{name:'重试',exact:true}).click();
  await page.getByText('这次答案已收到。',{exact:true}).waitFor();
  assert.equal(calls,11); assert.equal((await stored()).operation,null);
  assert.equal((await session()).turns.filter(t=>t.action==='answer'&&t.displayText==='10 元，先求单价').length,1);

  behavior = async () => question('check'); await send('再出一道题');
  await page.getByRole('button',{name:'开始检测',exact:true}).waitFor();
  await page.getByRole('button',{name:'开始检测',exact:true}).click();
  await latestQuestion().locator('textarea').fill('尚未提交就结束');
  const endingId = (await session()).check;
  await page.locator('.ai-close').click(); await page.locator('.bottom-input-bar').waitFor();
  record = await session(); assert.equal(record.phase,'ended'); assert.equal(record.check,null);
  assert.equal(record.turns.flatMap(t=>t.blocks||[]).find(b=>b.id===endingId).state,'skipped');
  assert.equal(await page.locator('.static-pane').innerText(),source);
  assert.equal(calls,12); assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,provider:'fixed',calls,checks:['start and draft restore','double submit','practice answer','help before feedback failure','help retry','stop while collapsed','late output rejected','lost answer response recovery','end check'],screenshots}));
} finally {
  releaseLate?.(reply('cleanup'));
  await browser.close(); await new Promise(r=>server.close(r));
  assert.ok(path.resolve(directory).startsWith(path.resolve(tmpdir())+path.sep));
  await rm(directory,{recursive:true,force:true});
}
