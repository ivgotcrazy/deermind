import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from '../../mvp_prototype/node_modules/playwright/index.mjs';
import {expect} from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import {createPrototypeServer} from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/student-state-review-20261024/',import.meta.url));
await mkdir(output,{recursive:true});
test('student state shares current personal examples and separates Belief from goal results',async t=>{
  const server=createPrototypeServer({directory:output,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model calls expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`,browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=(p,name)=>p.getByRole('button',{name,exact:true}),dialog=p=>p.getByRole('dialog'),tab=(p,name)=>p.getByRole('tab',{name,exact:true});
  const metric=(p,label)=>p.locator('.student-metrics .metric-card').filter({has:p.getByText(label,{exact:true})}).locator('strong');
  async function grant(p){const gate=p.locator('.access-gate');if(await gate.count()){await gate.getByLabel('用途',{exact:true}).fill('核对个人状态、采用范围与原始证据');await btn(gate,'记录用途并查看').click();await expect(gate).toHaveCount(0);}}
  async function journey(name,run,hash='students'){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'}),p=await ctx.newPage(),errors=[],calls=[];
      p.setDefaultTimeout(6000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
      try{await p.goto(base+'#/'+hash);await expect(p.locator('.student-state-workspace')).toBeVisible();await grant(p);await run(p);assert.deepEqual(errors,[]);assert.deepEqual(calls,[]);}
      catch(e){await p.screenshot({path:output+'/failure-'+name.slice(0,30).replace(/\W/g,'-')+'.png',fullPage:true});throw e;}
      finally{await ctx.close();}
    });
  }
  await journey('list filters counts and three level navigation',async p=>{
    await expect(metric(p,'示例学生')).toHaveText('2');await expect(metric(p,'期间学习活动')).toHaveText('3');await expect(metric(p,'当前人工疑点')).toHaveText('1');
    await expect(p.locator('.student-list')).toContainText('LEARNER-A');await expect(p.locator('.student-list')).not.toContainText('ST-001');
    await p.getByLabel('记录情况',{exact:true}).selectOption('without');await expect(p.locator('.student-list tbody tr')).toHaveCount(1);await expect(p.locator('.student-list')).toContainText('学生 B');
    await p.getByLabel('记录情况',{exact:true}).selectOption('review');await expect(p.locator('.student-list tbody tr')).toHaveCount(1);await expect(p.locator('.student-list')).toContainText('学生 A');
    await p.getByLabel('查找学生',{exact:true}).fill('LEARNER-A');await p.getByLabel('学生排序').selectOption('name');const listURL=p.url();await btn(p,'查看学生 LEARNER-A').click();await grant(p);
    await expect(p.locator('.student-space-list tbody tr')).toHaveCount(2);await expect(metric(p,'期间学习活动')).toHaveText('3');await expect(p.locator('.student-metrics')).not.toContainText('%');
    await p.screenshot({path:output+'/student-overview.png',fullPage:true});await btn(p,'查看空间状态 SPACE-001').click();await expect(p.locator('.student-beliefs')).toBeVisible();
    await btn(p,'← 返回学生概览').click();await expect(p.locator('.student-space-list')).toBeVisible();await btn(p,'← 返回学生列表').click();assert.equal(p.url(),listURL);
    await p.getByLabel('查找学生',{exact:true}).fill('未注册的名字');await expect(p.locator('.student-list tbody tr')).toHaveCount(0);await btn(p,'重置筛选').click();await expect(p.locator('.student-list tbody tr')).toHaveCount(2);
    await p.screenshot({path:output+'/student-list.png',fullPage:true});
  });
  await journey('space isolation and unknown aspects',async p=>{
    await expect(p.locator('.student-beliefs tbody tr')).toHaveCount(2);await expect(p.locator('.student-beliefs')).toContainText('只有受助完成记录');await expect(p.locator('.student-beliefs')).toContainText('面积公式的理由需加强');await expect(p.locator('.student-beliefs')).toContainText('尚未形成判断');
    await expect(p.locator('.student-targets tbody tr')).toHaveCount(8);await expect(p.locator('.goal-heading .result-badges')).toContainText('已达标 1');await expect(p.locator('.goal-heading .result-badges')).toContainText('待确认 6');
    await btn(p,'查看个人判断 CLAIM-GEOMETRY').click();await expect(dialog(p).locator('.belief-aspect')).toHaveCount(4);await expect(dialog(p)).toContainText('SPACE-EV-004');await expect(dialog(p)).not.toContainText('SPACE-EV-001');await expect(dialog(p).locator('.belief-aspect').filter({hasText:'迁移'})).toContainText('尚未形成判断');
    await expect(btn(dialog(p),'保存')).toHaveCount(0);await btn(p,'关闭对话框').click();await p.screenshot({path:output+'/student-space-state.png',fullPage:true});
    await p.goto(base+'#/students?id=LEARNER-A&scope=SPACE-002');await expect(p.locator('.student-beliefs tbody tr')).toHaveCount(1);await expect(p.locator('.student-beliefs')).not.toContainText('对明确给定底高的计算有支持');await expect(p.locator('.student-beliefs')).not.toContainText('面积公式的理由需加强');
    await expect(p.locator('.goal-heading .result-badges')).toContainText('待确认 4');await btn(p,'查看个人判断 CLAIM-GEOMETRY').click();await expect(dialog(p)).toContainText('0 条去重 Evidence');await btn(p,'关闭对话框').click();await tab(p,'学习活动').click();await expect(p.locator('.student-activities tbody tr')).toHaveCount(0);
  },'students?id=LEARNER-A&scope=SPACE-001');
  await journey('requirement standards are distinct from personal belief',async p=>{
    await btn(p,'查看学习要求 REQ-G1').click();await expect(dialog(p)).toContainText('已达标');await expect(dialog(p)).toContainText('对明确给定底高的计算有支持');await btn(dialog(p),'查看个人判断与证据').click();await expect(dialog(p)).toContainText('迁移');await expect(dialog(p)).toContainText('尚未形成判断');await btn(p,'关闭对话框').click();
    await btn(p,'查看学习要求 REQ-F1').click();await expect(dialog(p)).toContainText('待确认');await expect(dialog(p)).toContainText('教材采用的方法未完整覆盖');await expect(dialog(p)).toContainText('只有受助完成记录');await btn(p,'查看当前目标要求 →').click();await expect(btn(p,'← 返回学生状态')).toBeVisible();await btn(p,'← 返回学生状态').click();await expect(dialog(p)).toContainText('能独立求出增加后的数量');await btn(p,'关闭对话框').click();
    await p.getByLabel('教材章节',{exact:true}).selectOption('CH-TRIANGLE');await expect(p.locator('.student-beliefs tbody tr')).toHaveCount(1);await expect(p.locator('.student-targets tbody tr')).toHaveCount(4);
    await p.getByLabel('筛选 Task Claim').selectOption('CLAIM-FRACTION');await expect(p.locator('.student-beliefs tbody tr')).toHaveCount(0);await expect(p.locator('.student-targets tbody tr')).toHaveCount(0);
  },'students?id=LEARNER-A&scope=SPACE-001');
  await journey('evidence trace retains assistance and return context',async p=>{
    await p.getByLabel('筛选 Task Claim').selectOption('CLAIM-FRACTION');await btn(p,'查看个人判断 CLAIM-FRACTION').click();await btn(p,'SPACE-EV-001 · 查看依据 →').click();await expect(dialog(p)).toContainText('提示后完成，不支持独立完成');await expect(dialog(p)).toContainText('80 × 1/4');const source=p.url();
    await btn(p,'查看源活动的解释步骤 →').click();await expect(p.locator('.audit-step-detail h3')).toHaveText('解释 Evidence');await expect(p.locator('.round-button').nth(1)).toHaveAttribute('aria-pressed','true');await btn(p,'← 返回学生状态').click();assert.equal(p.url(),source);await expect(dialog(p)).toContainText('SPACE-EV-001');await btn(p,'关闭对话框').click();
    await expect(p.getByLabel('筛选 Task Claim')).toHaveValue('CLAIM-FRACTION');await p.reload();await expect(p.getByLabel('筛选 Task Claim')).toHaveValue('CLAIM-FRACTION');await expect(p.locator('.student-beliefs tbody tr')).toHaveCount(1);
  },'students?id=LEARNER-A&scope=SPACE-001');
  await journey('date scoped historical changes do not rewind current state',async p=>{
    await p.getByLabel('记录时间').selectOption('custom');await p.getByLabel('开始日期').fill('2026-10-23');await p.getByLabel('结束日期').fill('2026-10-23');await expect(p.locator('.goal-heading .result-badges')).toContainText('已达标 1');
    await tab(p,'变化与依据').click();await expect(p.locator('.student-changes tbody tr')).toHaveCount(1);await btn(p,'查看判断变化 SPACE-ACT-002:G-R1').click();await expect(dialog(p)).toContainText('对给定底高的独立计算有局部支持');await expect(dialog(p)).not.toContainText('已达标');await expect(dialog(p)).not.toContainText('SPACE-EV-003');const source=p.url();
    await btn(p,'追溯该轮 Belief 更新 →').click();await expect(p.locator('.audit-step-detail h3')).toHaveText('更新 Task Belief');await btn(p,'← 返回学生状态').click();assert.equal(p.url(),source);await btn(p,'关闭对话框').click();
    await p.getByLabel('记录时间').selectOption('all');await expect(p.locator('.student-changes tbody tr')).toHaveCount(3);await p.screenshot({path:output+'/belief-changes.png',fullPage:true});
    await p.getByLabel('记录时间').selectOption('custom');await p.getByLabel('开始日期').fill('2026-10-25');await expect(p.getByRole('alert')).toContainText('开始日期不能晚于结束日期');await expect(p.locator('.student-changes')).toHaveCount(0);
  },'students?id=LEARNER-A&scope=SPACE-001');
  await journey('current definition edits do not change adopted state or history',async p=>{
    const state=await p.locator('.student-beliefs').innerText(),goals=await p.locator('.student-targets').innerText();await btn(p,'查看个人判断 CLAIM-GEOMETRY').click();await btn(p,'查看当前 Claim 定义 →').click();await btn(p,'编辑基本定义').click();await dialog(p).getByLabel('Claim 名称').fill('只修改当前目录的名称');await btn(dialog(p),'保存').click();await btn(p,'← 返回学生状态').click();
    await expect(dialog(p)).toContainText('三角形面积求解 · 采用 v1');await expect(dialog(p)).not.toContainText('只修改当前目录的名称');await btn(p,'关闭对话框').click();assert.equal(await p.locator('.student-beliefs').innerText(),state);assert.equal(await p.locator('.student-targets').innerText(),goals);
    await tab(p,'变化与依据').click();await p.getByText('课程采用记录与当前定义差异',{exact:true}).click();await expect(p.locator('.definition-history')).toContainText('当前目录 v2');await expect(p.locator('.student-changes tbody tr')).toHaveCount(3);await btn(p,'查看采用内容与版本 →').click();await expect(btn(p,'← 返回学生状态')).toBeVisible();await btn(p,'← 返回学生状态').click();await expect(tab(p,'变化与依据')).toHaveAttribute('aria-selected','true');
  },'students?id=LEARNER-A&scope=SPACE-001');
  await journey('activities and cross page entry use the same student and space',async p=>{
    await tab(p,'学习活动').click();await expect(p.locator('.student-activities tbody tr')).toHaveCount(3);await btn(p,'SPACE-EV-004 →').click();await expect(dialog(p)).toContainText('为什么要除以 2');await btn(p,'关闭对话框').click();
    await btn(p,'查看活动 SPACE-ACT-003').click();await btn(p,'学生 A ↗').click();await expect(p.locator('.student-state-header')).toContainText('SPACE-001');await btn(p,'← 返回交互审查').click();await expect(p.locator('.activity-review-detail')).toContainText('SPACE-ACT-003');await btn(p,'← 返回学生状态').click();await expect(tab(p,'学习活动')).toHaveAttribute('aria-selected','true');
    await btn(p,'课程范围与采用版本 →').click();await btn(p,'学生状态 →').click();await expect(p.locator('.student-state-header')).toContainText('SPACE-001');await btn(p,'← 返回学习空间').click();await btn(p,'← 返回学生状态').click();
    await btn(p,'空间观测 →').click();await p.locator('.scope-context').getByRole('button',{name:'学生状态 →',exact:true}).click();await expect(p.locator('.student-state-header')).toContainText('SPACE-001');await btn(p,'← 返回空间观测').click();await expect(p.getByLabel('观测范围',{exact:true})).toHaveValue('SPACE-001');
  },'students?id=LEARNER-A&scope=SPACE-001');
  await journey('invalid references and other learners never substitute state',async p=>{
    await p.goto(base+'#/students?id=LEARNER-B&scope=SPACE-001');await expect(p.getByRole('alert')).toContainText('不属于这位学生');await expect(p.locator('.student-beliefs')).toHaveCount(0);
    await p.goto(base+'#/students?id=NOT-A-LEARNER');await expect(p.getByRole('alert')).toContainText('不在当前课程示例');
    await p.goto(base+'#/students?id=LEARNER-B&scope=SPACE-003');await grant(p);await expect(p.locator('.student-beliefs')).not.toContainText('对明确给定底高的计算有支持');await expect(p.locator('.goal-heading .result-badges')).toContainText('已达标 0');
    await p.goto(base+'#/students?id=LEARNER-B&scope=SPACE-003&result=evidence:SPACE-EV-002');await expect(dialog(p)).toContainText('不属于当前学习空间');await expect(dialog(p)).not.toContainText('42 平方厘米');await btn(p,'关闭对话框').click();
    await p.goto(base+'#/students?id=LEARNER-B&scope=SPACE-003&claim=CLAIM-COMPOSITE');await expect(p.getByRole('alert')).toContainText('不属于此空间');await expect(p.locator('.student-beliefs')).toHaveCount(0);
  });
  await journey('narrow layout and legacy real source boundaries',async p=>{
    await p.setViewportSize({width:1024,height:900});await expect(p.locator('.student-beliefs')).toBeVisible();assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);await p.screenshot({path:output+'/state-narrow-1024.png',fullPage:true});
    await btn(p,'查看个人判断 CLAIM-GEOMETRY').click();await p.screenshot({path:output+'/belief-detail.png',fullPage:true});await btn(p,'关闭对话框').click();
    await p.goto(base+'#/students');await p.getByText('示例范围',{exact:true}).click();await btn(p,'查看旧版个人记录 →').click();await expect(p.getByText(/旧版个人记录 · 与当前课程示例分开保留/)).toBeVisible();await expect(p.locator('.page-container')).toContainText('ST-001');await btn(p,'打开当前学生状态 →').click();await expect(p.locator('.student-list')).toContainText('LEARNER-A');
    await p.getByLabel('数据来源',{exact:true}).selectOption('real');await expect(p.getByRole('heading',{name:'尚未接入真实学生状态'})).toBeVisible();await expect(p.locator('.student-beliefs')).toHaveCount(0);await expect(p.locator('.student-list')).toHaveCount(0);
  },'students?id=LEARNER-A&scope=SPACE-001');
});
