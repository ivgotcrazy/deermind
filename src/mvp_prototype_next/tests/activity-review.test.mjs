import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir,readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { expect } from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/activity-review-20261024/',import.meta.url));
await mkdir(output,{recursive:true});
test('current interaction review connects activities, rounds, adopted definitions and personal results',async t=>{
  const server=createPrototypeServer({directory:output,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model calls expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`,browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=(p,name)=>p.getByRole('button',{name,exact:true}),tab=(p,name)=>p.getByRole('tab',{name,exact:true}),dialog=p=>p.getByRole('dialog');
  async function journey(name,run,hash='trace-list'){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'}),p=await ctx.newPage(),errors=[],calls=[];
      p.setDefaultTimeout(6000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
      try{await p.goto(base+'#/'+hash);await run(p);assert.deepEqual(errors,[]);assert.deepEqual(calls,[]);}
      catch(e){await p.screenshot({path:output+'/failure-'+name.slice(0,25).replace(/\W/g,'-')+'.png',fullPage:true});throw e;}
      finally{await ctx.close();}
    });
  }
  async function exported(p,label){const download=p.waitForEvent('download');await btn(p,label).click();return JSON.parse(await readFile(await (await download).path(),'utf8'));}
  await journey('list scope and separate status filters',async p=>{
    await expect(p.locator('.audit-list-table tbody tr')).toHaveCount(3);await expect(p.locator('.audit-metrics')).toContainText('4');
    await p.screenshot({path:output+'/list-desktop.png',fullPage:true});
    await p.getByLabel('学习空间',{exact:true}).selectOption('SPACE-002');await expect(p.locator('.audit-list-table tbody tr')).toHaveCount(0);
    await p.getByLabel('学生',{exact:true}).selectOption('LEARNER-B');await expect(p.locator('.audit-list-table tbody tr')).toHaveCount(0);
    await btn(p,'清除筛选').click();await p.getByLabel('审查情况',{exact:true}).selectOption('question');await expect(p.locator('.audit-list-table tbody tr')).toHaveCount(1);await expect(p.locator('.audit-list-table')).toContainText('处理完成');
    await p.getByLabel('执行状态',{exact:true}).selectOption('failed');await expect(p.locator('.audit-list-table tbody tr')).toHaveCount(0);
    await btn(p,'清除筛选').click();await p.getByLabel('搜索活动').fill('80 × 1/4');await expect(p.locator('.audit-list-table tbody tr')).toHaveCount(1);
    const index=await exported(p,'导出筛选结果 JSON');assert.deepEqual(index.items.map(i=>i.activityId),['SPACE-ACT-001']);assert.equal(index.items[0].rounds,2);
    await btn(p,'清除筛选').click();await p.getByLabel('时间段',{exact:true}).selectOption('custom');await p.getByLabel('开始日期').fill('2026-10-23');await p.getByLabel('结束日期').fill('2026-10-23');await expect(p.locator('.audit-list-table tbody tr')).toHaveCount(1);await expect(p.locator('.audit-list-table')).toContainText('独立计算三角形面积');
    await p.getByLabel('开始日期').fill('2026-10-25');await expect(p.getByRole('alert')).toContainText('开始日期不能晚于结束日期');await expect(btn(p,'导出筛选结果 JSON')).toBeDisabled();
  });
  await journey('space to activity preserves source and rounds',async p=>{
    await btn(p,'查看记录 提示后求增加后的水量').click();await btn(dialog(p),'进入交互审查 →').click();
    await expect(p.locator('.page-header')).toContainText('SPACE-ACT-001');await expect(p.locator('.round-button')).toHaveCount(2);
    await tab(p,'评价结果').click();await expect(p.locator('.page-container')).toContainText('本轮仅处理求助');await expect(p.locator('.round-beliefs')).toHaveCount(0);
    await p.locator('.round-button').nth(1).click();await expect(p.locator('.round-evidence')).toContainText('SPACE-EV-001');await expect(p.locator('.round-beliefs')).toContainText('只有受助完成记录');
    await tab(p,'交互过程').click();await expect(p.locator('.audit-step-detail h3')).toHaveText('校验候选：拒绝');await expect(p.locator('.audit-summary')).toContainText('处理完成');
    await p.locator('.prior-context summary').click();await expect(p.locator('.prior-context')).toContainText('先求增加的水');
    await p.locator('.waterfall').getByRole('button',{name:'提交 Observation',exact:true}).click();await expect(p.locator('.audit-step-detail')).toContainText('第 1 轮已展示');
    const url=p.url();await p.reload();assert.equal(p.url(),url);await expect(p.locator('.audit-step-detail h3')).toHaveText('提交 Observation');await expect(p.locator('.round-button').nth(1)).toHaveAttribute('aria-pressed','true');
    await btn(p,'← 返回学习空间').click();await expect(p.locator('.space-header')).toContainText('SPACE-001');await expect(tab(p,'学习记录')).toHaveAttribute('aria-selected','true');
  },'learning-spaces?id=SPACE-001&tab=records');
  await journey('historical belief evidence precedes later teaching',async p=>{
    await expect(p.locator('.round-beliefs')).toContainText('对给定底高的独立计算有局部支持');await expect(p.locator('.round-beliefs')).not.toContainText('SPACE-EV-003');await expect(p.locator('.round-results')).not.toContainText('已达标');
    await p.goto(base+'#/activity?id=SPACE-ACT-003&tab=evaluation');await expect(p.locator('.round-beliefs')).toContainText('SPACE-EV-002');await expect(p.locator('.round-results')).toContainText('需加强');await expect(p.locator('.round-results')).toContainText('已达标');
    await btn(p,'SPACE-EV-002 →').click();await expect(dialog(p)).toContainText('独立计算三角形面积');await btn(p,'查看源活动的解释步骤 →').click();await expect(p.locator('.page-header')).toContainText('SPACE-ACT-002');await expect(p.locator('.audit-step-detail h3')).toHaveText('解释 Evidence');
    await btn(p,'← 返回来源活动').click();await expect(p.locator('.page-header')).toContainText('SPACE-ACT-003');await expect(tab(p,'评价结果')).toHaveAttribute('aria-selected','true');
    await tab(p,'交互过程').click();await p.locator('.waterfall').getByRole('button',{name:'展示针对性讲解',exact:true}).click();await expect(p.locator('.audit-step-detail')).toContainText('尚无讲解后的新作答');
    await p.screenshot({path:output+'/feedback-desktop.png',fullPage:true});
  },'activity?id=SPACE-ACT-002&tab=evaluation');
  await journey('adopted definitions link owners and retain snapshot',async p=>{
    const rows=p.locator('.audit-definitions tbody tr');await expect(rows).toHaveCount(9);await expect(rows).not.toContainText(['花园']);
    for(const id of ['CH-TRIANGLE','TARGET-MATH','geometry','S2-A']){
      await btn(p,'查看采用内容 '+id).click();await btn(p,'查看当前定义 ↗').click();await expect(btn(p,'← 返回交互审查')).toBeVisible();await btn(p,'← 返回交互审查').click();await expect(tab(p,'采用定义')).toHaveAttribute('aria-selected','true');
    }
    await btn(p,'查看采用内容 CLAIM-GEOMETRY').click();const snapshot=await dialog(p).locator('.reference-fields').innerText();await btn(p,'查看当前定义 ↗').click();
    await btn(p,'编辑基本定义').click();await dialog(p).getByLabel('Claim 名称').fill('仅修改当前 Claim 名称');await btn(dialog(p),'保存').click();await btn(p,'← 返回交互审查').click();
    await btn(p,'查看采用内容 CLAIM-GEOMETRY').click();assert.equal(await dialog(p).locator('.reference-fields').innerText(),snapshot);await expect(dialog(p)).not.toContainText('仅修改当前 Claim 名称');
  },'activity?id=SPACE-ACT-003&tab=definitions&round=E-R1&span=E-R1-belief');
  await journey('review changes do not mutate learning outcomes',async p=>{
    const before=await exported(p,'导出本次示例 JSON');await tab(p,'审查记录').click();await btn(p,'保存审查记录').click();await expect(p.getByRole('alert')).toContainText('请填写复核结论');
    await p.getByLabel('审查结论').selectOption('recorded');await p.getByLabel('结论与依据').fill('核对两轮的提示时间与候选修正；目标方法范围仍需维护者确认。');await btn(p,'保存审查记录').click();
    const after=await exported(p,'导出本次示例 JSON');assert.equal(after.audit.review,'recorded');assert.deepEqual(after.audit.rounds,before.audit.rounds);assert.deepEqual(after.activity,before.activity);assert.equal(after.audit.execution,'completed');
    await btn(p,'← 返回交互审查').click();await p.getByLabel('搜索活动').fill('SPACE-ACT-001');await expect(p.locator('.audit-list-table')).toContainText('已记录复核');
  },'activity?id=SPACE-ACT-001');
  await journey('export references and timeline stay within the selected round',async p=>{
    const record=await exported(p,'导出本次示例 JSON');assert.equal(record.source,'authored-current-course-mock');assert.equal(record.space.id,'SPACE-001');
    const ids=new Set();for(const round of record.audit.rounds){const steps=new Map();function walk(list){for(const s of list){assert.ok(!ids.has(s.spanId));ids.add(s.spanId);steps.set(s.spanId,s);assert.ok(s.startTime+s.duration<=round.duration);for(const c of s.children||[])assert.ok(c.startTime>=s.startTime&&c.startTime+c.duration<=s.startTime+s.duration);walk(s.children||[]);}}walk(round.steps);for(const e of round.events)assert.ok(steps.has(e.spanId));}
    await p.locator('.timeline-disclosure summary').click();const round=record.audit.rounds[1];for(const e of round.events){await p.locator('.timeline-item').filter({hasText:e.label}).click();await expect(p.locator('.audit-step-detail h3')).toHaveText(e.label);}
    await p.locator('.waterfall').getByRole('button',{name:'LLM 调用：修正帮助条件',exact:true}).click();await expect(p.locator('.audit-step-detail')).toContainText('演示模型，未实际调用');await btn(p,'复制模型输出').click();await expect(p.locator('.audit-step-detail [role=status]')).toBeVisible();
    await p.locator('.waterfall').getByRole('button',{name:'校验候选：拒绝',exact:true}).click();await expect(p.locator('.audit-step-detail [role=status]')).toHaveCount(0);await p.screenshot({path:output+'/process-desktop.png',fullPage:true});
    await p.setViewportSize({width:1024,height:900});await expect(p.locator('.audit-step-detail')).toBeVisible();assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth>el.clientWidth),false);await p.screenshot({path:output+'/process-narrow.png',fullPage:true});
  },'activity?id=SPACE-ACT-001&round=F-R2');
  await journey('invalid references never substitute other activities',async p=>{
    await expect(p.locator('.page-container')).toContainText('未找到该活动');await expect(p.locator('.waterfall')).toHaveCount(0);
    await p.goto(base+'#/activity?id=SPACE-ACT-001&round=not-recorded');await expect(p.locator('.page-container')).toContainText('未找到该轮次');await expect(p.locator('.waterfall')).toHaveCount(0);
    await p.goto(base+'#/activity?id=SPACE-ACT-001&round=F-R1&span=F-R2-commit');await expect(p.locator('.detail-section')).toContainText('该步骤不属于本轮');await expect(p.locator('.audit-step-detail')).toHaveCount(0);
    await p.goto(base+'#/trace-list');await p.locator('.legacy-link summary').click();await btn(p,'查看旧版追溯示例 →').click();await expect(p.locator('[data-testid="trace-stats"]')).toBeVisible();
  },'activity?id=SPACE-ACT-missing');
});
