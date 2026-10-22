import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { expect } from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/space-observation-review/',import.meta.url));
const key='deermind-next-admin-workbench-v1';
await mkdir(output,{recursive:true});
test('space observation preserves scope, provenance and management boundaries',async t=>{
  const directory=await mkdtemp(path.join(tmpdir(),'deermind-observation-'));
  const server=createPrototypeServer({directory,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model call expected');}});
  server.listen(0,'127.0.0.1');await once(server,'listening');
  const base=`http://127.0.0.1:${server.address().port}/admin/`;
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));await rm(directory,{recursive:true,force:true});});
  async function context(hash='objects') {const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});const p=await ctx.newPage();p.setDefaultTimeout(5000);const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base+'#/'+hash);return {ctx,p,errors};}
  async function grant(p){const gate=p.locator('.access-gate');if(await gate.count()){await gate.getByLabel('用途',{exact:true}).fill('核对当前活动和所采用的历史定义');await gate.getByRole('button',{name:'记录用途并查看'}).click();await expect(gate).toHaveCount(0);}}
  function metric(p,label){return p.locator('[data-testid="observation-metrics"] .metric-card').filter({hasText:label}).locator('strong');}
  async function fixture(p,fn){const pending=p.waitForEvent('download');await p.getByRole('button',{name:'导出工作记录',exact:true}).click();const snapshot=await readFile(await (await pending).path(),'utf8');await p.evaluate(({key,code,snapshot})=>{const s=JSON.parse(localStorage.getItem(key)||snapshot);new Function('s',code)(s);localStorage.setItem(key,JSON.stringify(s));},{key,code:fn,snapshot});await p.reload();}

  await t.test('restores observation hierarchy instead of editable catalog',async()=>{
    const {ctx,p,errors}=await context();
    await expect(p.getByRole('navigation',{name:'观测空间'})).toBeVisible();
    await expect(p.getByRole('button',{name:'AI Reasoning',exact:true})).toBeVisible();
    await expect(p.locator('[data-testid="observation-metrics"]')).toBeVisible();
    await expect(p.getByRole('button',{name:'编辑',exact:true})).toHaveCount(0);
    await p.screenshot({path:path.join(output,'domain.png'),fullPage:true});
    assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('scope updates metrics, distributions and records without borrowing another space',async()=>{
    const {ctx,p,errors}=await context('objects?tab=Evaluation');
    await expect(metric(p,'Evidence 记录')).toHaveText('2');
    await p.getByLabel('观测范围',{exact:true}).selectOption('LS-002');
    await expect(metric(p,'Evidence 记录')).toHaveText('0');
    await expect(metric(p,'Belief 版本记录')).toHaveText('0');
    await expect(p.locator('tbody tr')).toHaveCount(0);
    await expect(p.locator('.dist-card').filter({hasText:'个人记录类型'}).locator('strong')).toHaveText(['0','0','0']);
    await expect(p.locator('.dist-card').filter({hasText:'个人记录的使用标记'}).locator('strong')).toHaveText(['0','0']);
    await p.getByLabel('观测范围',{exact:true}).selectOption('LS-001');
    await expect(metric(p,'Evidence 记录')).toHaveText('2');
    await p.getByLabel('筛选观测记录',{exact:true}).fill('EV-002');
    await expect(p.locator('tbody tr')).toHaveCount(1);
    await expect(metric(p,'Evidence 记录')).toHaveText('2');
    await p.reload();await expect(p.getByLabel('观测范围',{exact:true})).toHaveValue('LS-001');
    await p.screenshot({path:path.join(output,'evaluation-scope.png'),fullPage:true});
    await p.goto(base+'#/objects?tab=Evaluation&scope=LS-MISSING');
    await expect(p.getByRole('alert')).toContainText('不存在');await expect(metric(p,'Evidence 记录')).toHaveText('0');
    assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('historical versions and invalidated records remain traceable and read only',async()=>{
    const {ctx,p,errors}=await context('objects?tab=Evaluation&scope=LS-001');
    await fixture(p,"s.objects.push({...s.objects.find(o=>o.id==='EV-001'),version:2,name:'新解释版本'});s.activities[0].objects.push('EV-001@2');s.invalidated['EV-001@1']='核对发现帮助条件遗漏';s.objects.push({...s.objects.find(o=>o.id==='CL-001'),version:2,name:'新 Claim 定义'});");
    await expect(metric(p,'Evidence 记录')).toHaveText('3');await expect(metric(p,'已退出当前使用')).toHaveText('1');
    await p.getByRole('button',{name:'待复核：将提示后正确解释为独立支持',exact:true}).click();
    await expect(p).toHaveURL(/observed-object/);await grant(p);
    await expect(p.locator('.callout.danger')).toContainText('已退出当前使用');
    await expect(p.getByRole('button',{name:'编辑定义',exact:true})).toHaveCount(0);
    await p.getByRole('button',{name:'关联与来源',exact:true}).click();
    await p.getByRole('button',{name:/原量增减任务的多维能力声明 v1/}).click();
    await expect(p.getByRole('dialog')).toContainText('CL-001@1');
    await p.getByRole('button',{name:'打开完整详情',exact:true}).click();
    await expect(p).toHaveURL(/observed-object.*CL-001/);
    await expect(p.locator('.observation-detail')).toContainText('CL-001@1');
    await expect(p.locator('input[type=file]')).toHaveCount(0);
    await p.getByRole('button',{name:'前往评估模型管理 →',exact:true}).click();
    await expect(p.getByLabel('导入模型定义包')).toBeVisible();
    await expect(p.locator('.sidebar .nav-item.active')).toContainText('评估模型管理');
    await p.getByRole('button',{name:'← 返回观测详情',exact:true}).click();await expect(p).toHaveURL(/observed-object.*CL-001/);
    await p.getByRole('button',{name:'← 返回观测来源',exact:true}).click();
    await p.getByRole('button',{name:/提示后完成原量增减题 · ACT-001/}).click();
    await expect(p.getByRole('heading',{name:'原始输入与实际帮助',exact:true})).toBeVisible();
    assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('learning observes actual adoption and exposes missing references',async()=>{
    const {ctx,p,errors}=await context('objects?tab=Learning&scope=LS-002');
    await expect(metric(p,'活动记录')).toHaveText('0');
    await fixture(p,"s.spaces[1].adopted['MISSING']=7;s.objects.push({...s.objects.find(o=>o.id==='MAT-001'),version:2,name:'材料新版本'});");
    await expect(metric(p,'采用引用缺失')).toHaveText('1');
    await p.getByRole('button',{name:/^教材\s*1$/}).click();
    await expect(p.locator('tbody')).toContainText('MAT-001@1');await expect(p.locator('tbody')).not.toContainText('材料新版本');
    await p.getByRole('button',{name:'查看范围与采用版本 →',exact:true}).click();await grant(p);
    await expect(p.locator('.observation-detail')).toContainText('MISSING@7');
    await p.getByRole('button',{name:/MISSING@7 引用缺失/}).click();
    await expect(p.getByRole('dialog')).toContainText('没有可解析的对象版本');
    assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('runtime gaps remain unknown; existing activities can be traced',async()=>{
    const {ctx,p,errors}=await context('objects?tab=Reasoning&scope=LS-003');
    await expect(p.locator('[data-testid="observation-metrics"] strong')).toHaveText(['—','—','—','—']);
    await expect(p.locator('tbody tr')).toHaveCount(1);
    await p.getByRole('button',{name:'Validation 校验',exact:true}).click();
    await expect(p.getByRole('heading',{name:'Validation 校验日志尚未接入',exact:true})).toBeVisible();
    await p.screenshot({path:path.join(output,'reasoning.png'),fullPage:true});
    await p.getByRole('button',{name:'查看活动记录',exact:true}).click();await grant(p);
    await expect(p.locator('.page-container')).toContainText('请求讲解，尚未产生个人作答');
    await p.getByRole('button',{name:'← 返回来源',exact:true}).click();
    await expect(p.getByLabel('观测范围',{exact:true})).toHaveValue('LS-003');
    assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('missing activity results are exposed and do not crash provenance inspection',async()=>{
    const {ctx,p,errors}=await context('objects?tab=Interaction&scope=LS-003');
    await fixture(p,"s.activities.find(a=>a.id==='ACT-003').objects.push('EV-MISSING@1');");
    await expect(p.getByRole('status')).toContainText('活动存在结果引用缺失');
    await p.getByRole('button',{name:'查看本范围活动 →',exact:true}).click();
    await p.getByRole('button',{name:'请求讲解，尚未产生个人作答',exact:true}).click();await grant(p);
    await expect(p.getByRole('heading',{name:'结果记录缺失',exact:true})).toBeVisible();
    await expect(p.locator('.page-container')).toContainText('EV-MISSING@1');
    await p.getByRole('button',{name:'评价依据',exact:true}).click();
    await expect(p.locator('.page-container')).toContainText('无法确认本次是否形成');
    assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('pagination and owner editing preserve the observation return route',async()=>{
    const {ctx,p,errors}=await context();
    await fixture(p,"const source=s.objects.find(o=>o.id==='T-001');for(let n=0;n<32;n++)s.objects.push({...source,id:'EX-'+n,name:'额外任务'+n});");
    await p.getByLabel('筛选观测记录',{exact:true}).fill('额外任务');await p.getByRole('button',{name:'下一页',exact:true}).click();
    const url=p.url();await p.getByRole('button',{name:'查看记录',exact:true}).first().click();
    await p.getByRole('button',{name:'前往领域管理 →',exact:true}).click();
    await expect(p.locator('.sidebar .nav-item.active')).toContainText('领域管理');
    await p.getByRole('button',{name:'编辑',exact:true}).first().click();
    await p.getByRole('button',{name:'取消',exact:true}).click();
    await p.getByRole('button',{name:'← 返回观测详情',exact:true}).click();
    await p.getByRole('button',{name:'← 返回观测来源',exact:true}).click();
    assert.equal(p.url(),url);await expect(p.locator('tbody tr')).toHaveCount(10);
    await p.setViewportSize({width:1024,height:768});await p.screenshot({path:path.join(output,'narrow.png'),fullPage:true});
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);await ctx.close();
  });
  await t.test('legacy evolution is read only and real data never gets synthetic observations',async()=>{
    const {ctx,p,errors}=await context('objects?tab=Evolution');
    await fixture(p,"s.issues.push({id:'OLD-01',title:'历史核对',origin:'ACT-001',purpose:'核对',finding:'原记录',conclusion:'尚未解决',verdict:'open',baseVersion:1,sampleCases:[],impacts:[],log:[{at:'2026-10-20',text:'历史说明'}],dataMode:'demo'});");
    await p.getByRole('button',{name:/^历史演化事项\s*1$/}).click();await p.getByRole('button',{name:'查看历史记录',exact:true}).click();await grant(p);
    await expect(p.locator('.observation-detail')).toContainText('历史说明');
    await expect(p.getByRole('button',{name:/审核|批准|发布|保存/})).toHaveCount(0);
    await p.getByLabel('数据来源',{exact:true}).selectOption('real');
    await expect(p.getByRole('heading',{name:'尚未接入真实模型数据',exact:true})).toBeVisible();
    await expect(p.locator('.space-browser')).toHaveCount(0);
    assert.deepEqual(errors,[]);await ctx.close();
  });
});
