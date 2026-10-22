import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, rm, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { expect } from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/interaction-review/',import.meta.url));
const key='deermind-next-admin-workbench-v1';
await mkdir(output,{recursive:true});
test('interaction review restores the original process inspection workflow',async t=>{
  const directory=await mkdtemp(path.join(tmpdir(),'deermind-trace-review-'));
  const server=createPrototypeServer({directory,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model call expected');}});
  server.listen(0,'127.0.0.1');await once(server,'listening');
  const base=`http://127.0.0.1:${server.address().port}/admin/`;
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));assert.ok(directory.startsWith(path.join(tmpdir(),'deermind-trace-review-')));await rm(directory,{recursive:true,force:true});});
  async function context(hash='trace-list'){const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'});const p=await ctx.newPage();p.setDefaultTimeout(5000);const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base+'#/'+hash);return {ctx,p,errors};}
  async function grant(p){const gate=p.locator('.access-gate');if(await gate.count()){await gate.getByLabel('用途',{exact:true}).fill('对照原版审查处理过程');await gate.getByRole('button',{name:'记录用途并查看'}).click();await expect(gate).toHaveCount(0);}}
  async function snapshot(p){const pending=p.waitForEvent('download');await p.getByRole('button',{name:'导出工作记录',exact:true}).click();return JSON.parse(await readFile(await (await pending).path(),'utf8'));}
  await t.test('list restores scope statistics, student, space, status and functional dates',async()=>{
    const {ctx,p,errors}=await context();
    await expect(p.locator('[data-testid="trace-stats"]')).toBeVisible();
    await p.getByLabel('学生',{exact:true}).selectOption('ST-002');await expect(p.locator('tbody tr')).toHaveCount(1);
    await p.getByLabel('学生',{exact:true}).selectOption('ST-001');await p.getByLabel('学习空间',{exact:true}).selectOption('LS-002');await expect(p.locator('tbody tr')).toHaveCount(0);
    await p.getByLabel('学习空间',{exact:true}).selectOption('LS-001');await p.getByLabel('处理状态',{exact:true}).selectOption('partial');await expect(p.locator('tbody tr')).toHaveCount(1);
    await p.getByLabel('时间段',{exact:true}).selectOption('custom');await p.getByLabel('开始日期',{exact:true}).fill('2026-10-21');await p.getByLabel('结束日期',{exact:true}).fill('2026-10-22');await expect(p.locator('tbody tr')).toHaveCount(0);
    await p.getByLabel('开始日期',{exact:true}).fill('2026-10-20');await expect(p.locator('tbody tr')).toHaveCount(1);
    await p.screenshot({path:path.join(output,'list.png'),fullPage:true});assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('detail restores side by side stages, rejection, retry and recorded outputs',async()=>{
    const {ctx,p,errors}=await context('activity?id=ACT-001&scope=ACT-001&returnTo=%23%2Ftrace-list');await grant(p);
    await expect(p.locator('.trace-main .waterfall')).toBeVisible();await expect(p.locator('.trace-main .span-detail')).toBeVisible();
    await p.locator('.waterfall-row').filter({hasText:'校验候选：拒绝'}).click();await expect(p.locator('.span-detail')).toContainText('实际已提供列式提示');
    await p.locator('.waterfall-row').filter({hasText:'LLM 调用：修正观察'}).click();await expect(p.locator('.span-detail')).toContainText('输入 tokens');await expect(p.locator('.span-detail')).toContainText('受助');
    await p.locator('.waterfall-row').filter({hasText:'推断 Task Belief'}).click();await expect(p.locator('.span-detail')).toContainText('延迟保持');await expect(p.locator('.span-detail')).toContainText('证据不足');
    const left=await p.locator('.waterfall-section').boundingBox(),right=await p.locator('.detail-section').boundingBox();assert.ok(right.x>=left.x+left.width-1);
    await p.screenshot({path:path.join(output,'belief.png'),fullPage:true});
    await p.locator('.timeline-item').filter({hasText:'候选被拒绝'}).click();await expect(p.locator('.span-detail')).toContainText('实际已提供列式提示');
    await p.screenshot({path:path.join(output,'rejection.png'),fullPage:true});assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('each activity has its own trace and unknown records never reuse another trace',async()=>{
    const {ctx,p,errors}=await context('activity?id=ACT-002&scope=ACT-002');await grant(p);await expect(p.locator('.trace-detail')).toContainText('100 ÷ (1 + 1/4)');await expect(p.locator('.waterfall-row').filter({hasText:'校验候选：拒绝'})).toHaveCount(0);
    await p.goto(base+'#/activity?id=ACT-003&scope=ACT-003');await grant(p);await expect(p.locator('.trace-detail')).toContainText('尚无系统输出记录');await expect(p.locator('.waterfall-row').filter({hasText:'推断 Task Belief'})).toHaveCount(0);
    await p.goto(base+'#/activity?id=UNKNOWN');await expect(p.locator('.page-container')).toContainText('不存在');assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('scope and step selection survive navigation, refresh and historical reference lookup',async()=>{
    const {ctx,p,errors}=await context('trace-list?filter=LS-001&status=partial');const list=p.url();await p.getByRole('button',{name:'提示后完成原量增减题',exact:true}).click();await grant(p);
    await p.locator('.waterfall-row').filter({hasText:'解释 Evidence'}).click();await p.reload();await expect(p.locator('.span-detail')).toContainText('解释 Evidence');
    await p.locator('.span-detail').getByRole('button',{name:/待复核：将提示后正确解释为独立支持/}).click();await p.getByRole('button',{name:'打开完整详情',exact:true}).click();await expect(p.locator('.observation-detail')).toContainText('EV-001');
    await p.getByRole('button',{name:'← 返回观测来源',exact:true}).click();await expect(p.locator('.span-detail')).toContainText('解释 Evidence');await p.getByRole('button',{name:'← 返回来源',exact:true}).click();assert.equal(p.url(),list);assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('missing references and absent process data stay explicit; long lists paginate',async()=>{
    const {ctx,p,errors}=await context();const s=await snapshot(p);s.activities[0].objects.push('EV-MISSING@1');for(let n=0;n<22;n++)s.activities.push({...s.activities[1],id:'ACT-EXTRA-'+n,name:'新增活动'+n});await p.evaluate(({key,s})=>localStorage.setItem(key,JSON.stringify(s)),{key,s});await p.reload();await expect(p.locator('tbody tr')).toHaveCount(10);await p.getByRole('button',{name:'下一页',exact:true}).click();await expect(p.locator('tbody tr')).toHaveCount(10);
    await p.goto(base+'#/activity?id=ACT-EXTRA-1');await grant(p);await expect(p.locator('.page-container')).toContainText('尚无处理步骤记录');await expect(p.locator('.waterfall')).toHaveCount(0);
    await p.goto(base+'#/activity?id=ACT-001');await grant(p);await expect(p.getByRole('heading',{name:'结果记录缺失',exact:true})).toBeVisible();assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('real sessions remain read only and never receive synthetic traces or formal beliefs',async()=>{
    const sample={version:2,revision:1,id:'NEXT-trace-real-fixture',scope:{space:'math-6b',label:'六年级下册数学'},model:'fixture',phase:'learning',pending:null,error:null,createdAt:'2026-10-21T09:00:00+08:00',updatedAt:'2026-10-21T09:00:03+08:00',turns:[{id:'u1',role:'user',text:'解释圆柱体积',at:'2026-10-21T09:00:00+08:00'},{id:'a1',role:'assistant',blocks:[{type:'explanation',text:'底面积乘高。'}],at:'2026-10-21T09:00:03+08:00',metrics:{ms:2100,calls:[{ms:1900,usage:{prompt_tokens:60,completion_tokens:30},finish:'stop'}]}}],requests:{}};
    const file=path.join(directory,sample.id+'.json'),raw=JSON.stringify(sample);await writeFile(file,raw);
    const {ctx,p,errors}=await context();await p.getByLabel('数据来源',{exact:true}).selectOption('real');await expect(p.getByLabel('学生',{exact:true})).toBeDisabled();await p.getByRole('button',{name:'解释圆柱体积',exact:true}).click();await grant(p);
    await expect(p.locator('.page-container')).toContainText('2.10 秒');await expect(p.locator('.page-container')).toContainText('没有逐条展示回执');await expect(p.locator('.waterfall')).toHaveCount(0);await expect(p.locator('.page-container')).not.toContainText('BL-001');await p.screenshot({path:path.join(output,'real.png'),fullPage:true});assert.equal(await readFile(file,'utf8'),raw);assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('desktop narrow layout stays usable without document overflow',async()=>{
    const {ctx,p,errors}=await context('activity?id=ACT-001');await grant(p);await p.setViewportSize({width:1024,height:768});await expect(p.locator('.span-detail')).toBeVisible();assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.screenshot({path:path.join(output,'narrow.png'),fullPage:true});assert.deepEqual(errors,[]);await ctx.close();
  });
});
