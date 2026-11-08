import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { chromium, expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

const expect=baseExpect.configure({timeout:8000});
const source=await readFile(new URL('../src/model/learning-spaces.ts',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const model=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));

test('space snapshots preserve event identity, references, corrections and assessment scope',()=>{
  for(const s of model.learningSpaces){
    const ids=new Set(s.events.map(e=>e.id));assert.equal(ids.size,s.events.length);
    const cells=new Set(s.tasks.flatMap(t=>t.methods.flatMap(m=>m.cells.map(c=>c.key))));
    for(const e of s.events){
      assert.ok(e.id.startsWith(s.id+'-'));assert.ok(Object.isFrozen(e));assert.ok(Object.isFrozen(e.fields));
      for(const id of e.causes){assert.ok(ids.has(id));assert.ok(s.events.find(x=>x.id===id).sequence<e.sequence);}
      e.cells.forEach(key=>assert.ok(cells.has(key)));
    }
    for(const t of s.tasks)for(const m of t.methods)for(const c of m.cells){if(c.eventId){const event=s.events.find(e=>e.id===c.eventId);assert.ok(event);assert.equal(event.type,'目标状态更新');assert.ok(event.cells.includes(c.key));}}
  }
  const s=model.learningSpaces[0],before=JSON.stringify(s);
  assert.throws(()=>s.events.splice(0,1),TypeError);
  assert.throws(()=>{s.events[0].summary='overwrite';},TypeError);
  assert.throws(()=>{s.events[0].fields[0].value='overwrite';},TypeError);
  const retention='TT-QUARTER-S1:retention';
  assert.ok(model.relatedEvents(s,retention).has('LS-001-015'));
  assert.ok(model.linkedCells(s,'LS-001-015').includes(retention));
  assert.equal(model.taskResult(s.tasks[0]),'需加强');
  const copy=structuredClone(s.tasks[0]);copy.methods[0].cells.forEach(c=>c.status='已达标');
  assert.equal(model.taskResult(copy),'待确认'); // One method cannot stand in for both.
  copy.mode='any';assert.equal(model.taskResult(copy),'已达标');
  assert.equal(model.latestLearning(s),'2026-11-08 09:26:00');
  assert.equal(model.latestEvaluation(s),'2026-11-08 09:15:02');
  const old=s.events.find(e=>e.id==='LS-001-017');assert.ok(!JSON.stringify(old.fields).includes('纠正'));
  assert.equal(before,JSON.stringify(s));
});

test('learning spaces read-only end-to-end review',async t=>{
  const server=createPreviewServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
  const page=await context.newPage();page.setDefaultTimeout(8000);
  const errors=[],api=[];page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/api/**',r=>{api.push(r.request().url());return r.abort();});
  t.after(async()=>{await browser.close();await new Promise(resolve=>server.close(resolve));});
  const base='http://127.0.0.1:'+server.address().port;
  const output=fileURLToPath(new URL('../test-results/learning-spaces/',import.meta.url));await mkdir(output,{recursive:true});
  const go=query=>page.goto(base+'/admin/#/learning-spaces'+(query?'?'+query:''));
  const btn=name=>page.getByRole('button',{name,exact:true});
  const dialog=()=>page.getByRole('dialog');
  const dBtn=name=>dialog().getByRole('button',{name,exact:true});
  const shot=async name=>{await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:output+name+'.png',animations:'disabled'});};
  const independent='先求增加量，再求新量 · 独立 · 已达标';
  const retention='先求增加量，再求新量 · 保持 · 需加强';
  const transfer='先求增加量，再求新量 · 迁移 · 待确认';

  await t.test('entry, list filters, pagination and same-name students remain distinct',async()=>{
    await go('');await expect(page.getByRole('navigation',{name:'后台导航'}).getByRole('button',{name:'学习空间',exact:true})).toHaveAttribute('aria-current','page');
    await expect(page.locator('.data-table tbody tr')).toHaveCount(2);
    await expect(page.locator('.data-table')).toContainText('student-001');await expect(page.locator('.data-table')).toContainText('student-002');
    await shot('01-space-list');await btn('下一页').click();await expect(page.locator('.data-table')).toContainText('LS-003');
    await btn('进入 LS-003').click();await expect(btn('学习目标')).toHaveAttribute('aria-current','page');
    await btn('数据的表示（综合应用）').click();await expect(page.locator('.goal-matrix')).toContainText('本目标未要求');
    await btn('← 返回学习空间列表').click();await expect(page.locator('.pagination')).toContainText('2 / 2');
    await page.getByLabel('学生',{exact:true}).fill('student-002');await btn('查询').click();await expect(page.locator('.data-table tbody tr')).toHaveCount(1);await btn('进入 LS-002').click();
    await expect(page.locator('.goal-matrix')).not.toContainText('已达标');await btn('空间事件').click();await expect(page.locator('.event-table tbody tr')).toHaveCount(2);await expect(page.locator('.event-table')).not.toContainText('LS-001');
    await btn('← 返回学习空间列表').click();await expect(page.getByLabel('学生',{exact:true})).toHaveValue('student-002');
    await btn('重置').click();await expect(page.getByLabel('学生',{exact:true})).toHaveValue('');
  });

  await t.test('adopted textbook pages, chapter context and target definition are read-only',async()=>{
    await go('id=LS-001');await btn('教材').click();await btn('第 49 页 · 放大查看').click();
    await expect(dialog().getByRole('img')).toBeVisible();assert.ok(await dialog().getByRole('img').evaluate(i=>i.complete&&i.naturalWidth>0));await btn('关闭对话框').click();
    await btn('数据的表示（综合应用）').click();await expect(page.locator('.page-thumb')).toHaveCount(3);await shot('02-adopted-textbook');
    await btn('本章目标 →').click();await expect(page.getByText('本目标未选用本章任务。教材包含本章，不代表本目标要求评价本章。')).toBeVisible();
    await btn('分数的应用').click();await expect(page.locator('.goal-matrix')).toBeVisible();await btn('查看目标定义').click();await expect(dialog()).toContainText('所选方法分别达标');await expect(dialog().getByRole('button',{name:/保存|删除|编辑/})).toHaveCount(0);await btn('关闭对话框').click();
    await shot('03-goal-method-matrix');await page.reload();await expect(page.locator('.goal-matrix')).toBeVisible();
  });

  await t.test('goal to update, evaluation and original answer, then back to exact goal cell',async()=>{
    await go('id=LS-001');await btn(independent).click();await expect(dialog()).toContainText('2 道不同新题');await btn('查看本次目标更新事件').click();
    await expect(dialog()).toContainText('LS-001-013');await dialog().getByRole('button',{name:'两道新题支持方法一的独立求解与解释',exact:true}).click();
    await expect(dialog()).toContainText('EVD-01');await dialog().getByRole('button',{name:'120 本书：提交 150 本并解释',exact:true}).click();
    await expect(dialog()).toContainText('120 ÷ 4 = 30');await expect(dialog()).toContainText('本轮未展示当题提示');await expect(dialog()).toContainText('关联的当前目标项');
    await dialog().getByRole('button',{name:'先求增加量，再求新量 · 独立 → 已达标',exact:true}).click();await expect(dialog()).toContainText('目标项与判断依据');await expect(dialog()).toContainText('独立');
    await btn('查看相关事件').click();await expect(dialog()).toHaveCount(0);await expect(page.locator('.callout')).toContainText('正在追溯');
    await btn('返回目标项').click();await expect(dialog()).toContainText('独立');await btn('关闭对话框').click();
  });

  await t.test('correction preserves old result and leads to different current state',async()=>{
    await go('id=LS-001');await btn(retention).click();await expect(dialog()).toContainText('旧的通过结果已被后续纠正');await btn('查看本次目标更新事件').click();await expect(dialog()).toContainText('LS-001-021');
    await dBtn('重新判断：遗漏加回原量').click();await dBtn('撤销错误解释并追加更正').click();await dBtn('当时将保持改为已达标').click();
    await expect(dialog().locator('.detail-section').first()).toContainText('保持：待确认 → 已达标');await expect(dialog()).toContainText('后续关联');await expect(dialog()).toContainText('先求增加量，再求新量 · 保持 → 需加强');
    await shot('04-historical-result-and-correction');await dBtn('保持检测评价通过').click();await expect(dialog().locator('.detail-section').first()).toContainText('判定通过');await expect(dialog().locator('.detail-section').first()).not.toContainText('纠正');
    await btn('← 返回上一条查看记录').click();await expect(dialog()).toContainText('LS-001-018');await btn('查看前后事件').click();await expect(dialog()).toHaveCount(0);await expect(page.locator('[data-event="LS-001-018"]')).toContainText('当前定位');
    await btn('返回目标项').click();await expect(dialog()).toContainText('需加强');
  });

  await t.test('help ends the round before child teaching and has no false independent pass',async()=>{
    await go('id=LS-001&tab=events');await page.getByLabel('活动',{exact:true}).selectOption('ACT-04 迁移检测');await btn('查询事件').click();
    await btn('R4 因求助结束，未提交答案').click();await expect(dialog()).toContainText('不作为独立通过或答错');await dBtn('检测轮结束后进入讲解').click();await expect(dialog()).toContainText('父活动');await expect(dialog()).toContainText('ACT-04 迁移检测');await dBtn('解释表格中的原量与增加比例').click();await expect(dialog()).toContainText('R4 已结束后才展示提示');
    await btn('关闭对话框').click();await btn('学习目标').click();await btn(transfer).click();await expect(dialog()).toContainText('新作答评价失败');await expect(dialog()).toContainText('待确认');await btn('查看相关事件').click();
    await btn('新作答评价未完成').click();await expect(dialog()).toContainText('不覆盖已有目标状态');await dBtn('表格新题提交 50 千克').click();await expect(dialog()).toContainText('此前刚讲解过同类表格表达');await expect(dialog().getByRole('table')).toContainText('40');await expect(dialog().getByRole('table')).toContainText('？');await shot('05-answer-trace');
    await expect(dialog().getByRole('button',{name:/保存|编辑|删除|重试/})).toHaveCount(0);
  });

  await t.test('filters, late event timing, stable order and refresh retain navigation',async()=>{
    await go('id=LS-001&tab=events');await expect(page.locator('.event-table tbody tr').first()).toHaveAttribute('data-event','LS-001-033');await expect(page.locator('.event-table tbody tr').first()).toContainText('补录于 2026-11-08 09:27:00');
    await page.getByLabel('发生日期从',{exact:true}).fill('2026-11-09');await page.getByLabel('至',{exact:true}).fill('2026-11-01');await btn('查询事件').click();await expect(page.getByRole('alert')).toContainText('开始日期不能晚于结束日期');
    await page.getByLabel('发生日期从',{exact:true}).fill('2026-11-01');await page.getByLabel('至',{exact:true}).fill('2026-11-01');await page.getByLabel('事件类别',{exact:true}).selectOption('操作与作答');await btn('查询事件').click();await expect(page.locator('.event-table tbody tr')).toHaveCount(2);
    await page.reload();await expect(page.getByLabel('事件类别',{exact:true})).toHaveValue('操作与作答');await expect(page.locator('.event-table tbody tr')).toHaveCount(2);
    await btn('教材').click();await btn('空间事件').click();await expect(page.locator('.event-table tbody tr')).toHaveCount(2);
    await btn('重置筛选').click();await shot('06-events');await btn('下一页').click();await page.reload();await expect(page.locator('.pagination')).toContainText('2 / '+Math.ceil(model.learningSpaces[0].events.length/8));
    await go('id=LS-002&tab=events&event=LS-001-015');await expect(page.getByRole('alert')).toContainText('不属于当前学习空间');await expect(dialog()).toHaveCount(0);
    await go('id=missing');await expect(page.getByRole('heading',{name:'未找到学习空间'})).toBeVisible();
  });

  await t.test('existing navigation remains available and no backend is called',async()=>{
    await page.getByRole('navigation',{name:'后台导航'}).getByRole('button',{name:'教材管理',exact:true}).click();await expect(page.getByRole('heading',{name:'教材管理',exact:true})).toBeVisible();
    await page.getByRole('navigation',{name:'后台导航'}).getByRole('button',{name:'领域管理',exact:true}).click();await expect(page.getByRole('heading',{name:'领域管理',exact:true})).toBeVisible();
    assert.deepEqual(api,[]);assert.deepEqual(errors,[]);
  });
});
