import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium, expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';
const expect=baseExpect.configure({timeout:10000});
const output=fileURLToPath(new URL('../test-results/extracted-instances/',import.meta.url));
test('extract textbook objects before assigning templates; solutions retain distinct provenance',async t=>{
  await mkdir(output,{recursive:true});const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base='http://127.0.0.1:'+server.address().port,browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'}),page=await context.newPage();page.setDefaultTimeout(10000);
  const errors=[],api=[];page.on('pageerror',e=>errors.push(e.message));await context.route('**/api/**',r=>{api.push(r.request().url());return r.abort();});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=name=>page.getByRole('button',{name,exact:true});
  const state=()=>page.evaluate(()=>({imports:JSON.parse(localStorage.getItem('deermind-m1-import-v1')||'[]'),domain:JSON.parse(localStorage.getItem('deermind-m1-domain-v1')||'{}')}));
  const entry=async id=>(await state()).imports[0].integration.entries.find(e=>e.id===id);
  const tab=prefix=>page.getByRole('navigation',{name:'提取对象类型'}).getByRole('button',{name:new RegExp('^'+prefix)});
  const select=async title=>{await btn('内容提取').click();await page.locator('.integration-entry').filter({hasText:title}).click();};
  const shot=async name=>{await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:output+name+'.png',animations:'disabled'});};
  const confirm=async()=>{await btn('确认本项提取结果').click();await btn('匹配或补建模板').click();};
  let sourceSolutions,practiceId;

  await t.test('empty-domain extraction contains KC candidates, one example and its two actual solutions',async()=>{
    await page.goto(base+'/admin/#/textbooks');await btn('导入教材').click();await page.getByText('Mock处理场景',{exact:true}).click();await btn('空领域新建').click();await btn('上传并开始整理').click();
    await expect(btn('确认本项提取结果')).toBeVisible();
    await expect(tab('知识 KC')).toContainText('3');await expect(tab('题目 TaskInstance')).toContainText('1');await expect(tab('解法 SolutionInstance')).toContainText('2');
    const s=await state(),e=await entry('MAT-GROUPS');assert.equal(s.domain.tasks.length,0);assert.equal(s.domain.methods.length,0);assert.equal(s.domain.instances.length,0);
    assert.equal(e.solutionInstances.length,2);assert.ok(e.solutionInstances.every(x=>x.taskInstanceId===e.taskInstance.id&&x.origin==='教材原有'));
    sourceSolutions=JSON.stringify(e.solutionInstances);
    await tab('知识 KC').click();await expect(page.getByRole('table',{name:'提取的KC'}).locator('tbody tr')).toHaveCount(3);await shot('01-kc');
    await tab('解法 SolutionInstance').click();await expect(page.getByRole('table',{name:'提取的SolutionInstance'}).locator('tbody tr')).toHaveCount(2);await shot('02-source-solutions');
    await btn('核对解法 '+e.solutionInstances[0].id).click();await expect(page.getByRole('dialog')).toContainText('教材原有');await expect(page.getByLabel('本题具体求解过程',{exact:true})).toHaveValue(/12×1\/3=4/);await btn('取消').click();
    await confirm();await btn('补齐缺少的模板与知识（mock）').click();
    assert.equal((await state()).domain.instances.length,0);assert.equal((await entry('MAT-GROUPS')).solutionInstances.length,2);
    await btn('检查并保存实例（mock）').click();await btn('保存本项映射').click();await expect(page.getByRole('alert')).toHaveCount(0);
    const q=(await state()).domain.instances[0];assert.equal(q.solutions.length,2);assert.ok(q.solutions.every(x=>x.id&&x.taskInstanceId===q.id&&x.origin==='教材原有'));
  });

  await t.test('practice extracts no solutions or answers; a template alone does not create one',async()=>{
    await select('试一试①');await expect(tab('解法 SolutionInstance')).toContainText('0');await expect(page.getByText('未提供／尚未提取。题目可以先保留，不自动编造解法。',{exact:true})).toBeVisible();
    await expect(page.locator('.integration-entry').filter({hasText:'试一试'})).toHaveCount(3);
    const e=await entry('MAT-MIXED');practiceId=e.taskInstance.id;assert.equal(e.answer,'');assert.deepEqual(e.solutionInstances,[]);
    await btn('查看原页并核对').click();await expect(page.locator('[data-block="B-TRY"]')).toBeVisible();await expect(page.locator('[data-block="B-METHOD-A"]')).toHaveCount(0);await btn('内容提取').click();
    await shot('03-practice');await confirm();await btn('补齐缺少的模板与知识（mock）').click();
    assert.deepEqual((await entry('MAT-MIXED')).solutionInstances,[]);
    await btn('保存实例草稿').click();let q=(await state()).domain.instances.find(q=>q.id===practiceId);assert.equal(q.answer,'');assert.deepEqual(q.solutions,[]);assert.equal(q.checkedSignature,'');
    await btn('检查并保存实例（mock）').click();await expect(page.getByRole('alert')).toContainText('参考');
    await btn('保存本项映射').click();await expect(page.getByRole('alert')).toContainText('题目仍需');
  });

  await t.test('generation has a cancel and failed-check path; success keeps the same question',async()=>{
    await btn('补充参考解法（mock）').click();await btn('生成解法候选').click();await expect(page.getByLabel('生成的结果',{exact:true})).toHaveValue('40');await shot('04-generation');
    await btn('取消').click();assert.deepEqual((await entry('MAT-MIXED')).solutionInstances,[]);
    await btn('补充参考解法（mock）').click();await btn('生成解法候选').click();await page.getByLabel('模拟解法检查',{exact:true}).selectOption('fail');await btn('检查并采用（mock）').click();
    await expect(page.getByRole('dialog').getByRole('alert')).toContainText('未采用');assert.deepEqual((await entry('MAT-MIXED')).solutionInstances,[]);
    await page.getByLabel('模拟解法检查',{exact:true}).selectOption('pass');await btn('检查并采用（mock）').click();
    const e=await entry('MAT-MIXED');assert.equal(e.answer,'');assert.equal(e.solutionInstances.length,1);assert.equal(e.solutionInstances[0].origin,'系统生成');assert.equal(e.solutionInstances[0].taskInstanceId,practiceId);
    await btn('检查并保存实例（mock）').click();await btn('保存本项映射').click();await expect(page.getByRole('alert')).toHaveCount(0);
    let s=await state(),q=s.domain.instances.find(x=>x.id===practiceId);assert.equal(s.domain.instances.filter(x=>x.id===practiceId).length,1);assert.equal(q.answer,'40');assert.equal(q.solutions[0].origin,'系统生成');
    await btn('查看已保存题目').click();await expect(page.getByRole('dialog')).toContainText('系统生成');await btn('预览学生题面').click();await expect(page.getByTestId('student-question')).not.toContainText('40');await btn('关闭对话框').click();await btn('← 返回本项融合').click();
    await select('三个兴趣小组');assert.equal(JSON.stringify((await entry('MAT-GROUPS')).solutionInstances),sourceSolutions);
    await select('试一试①');await tab('解法 SolutionInstance').click();await expect(page.getByRole('table',{name:'提取的SolutionInstance'})).toContainText('系统生成');await page.reload();await tab('解法 SolutionInstance').click();await shot('05-generated-source');
  });

  await t.test('a pure knowledge statement needs no fabricated task or solution instance',async()=>{
    await select('知识：除以非零数');await expect(tab('题目 TaskInstance')).toContainText('0');await expect(tab('解法 SolutionInstance')).toContainText('0');
    await expect(page.getByRole('table',{name:'提取的KC'})).toContainText('除以一个不为零的数');const before=(await state()).domain;
    await confirm();await btn('补齐缺少的模板与知识（mock）').click();const after=(await state()).domain;
    assert.equal(after.knowledge.length,before.knowledge.length+1);assert.equal(after.tasks.length,before.tasks.length);assert.equal(after.methods.length,before.methods.length);assert.equal(after.instances.length,before.instances.length);
    await page.getByRole('navigation',{name:'导入工作区'}).getByRole('button',{name:'检查并应用',exact:true}).click();await expect(btn('模拟应用本项内容')).toBeDisabled();await expect(page.getByText(/此项只提取了 KC/)).toBeVisible();
  });

  await t.test('a solution cannot be saved against a method outside its Task',async()=>{
    await select('三个兴趣小组');await btn('匹配或补建模板').click();const practice=await entry('MAT-MIXED'),methodId=practice.bindings.methodCalc.id;
    await btn('选择已有 methodA').click();await page.getByLabel('已有对象',{exact:true}).selectOption(methodId);await btn('复用所选对象').click();await btn('检查并保存实例（mock）').click();await expect(page.getByRole('alert')).toContainText('参考方法不在当前任务');
  });

  await t.test('legacy drafts preserve text and references without inventing provenance',async()=>{
    const before=await state(),old=before.imports[0],e=old.integration.entries.find(x=>x.id==='MAT-GROUPS');
    const references=JSON.stringify(e.bindings),domain=JSON.stringify(before.domain);
    delete e.extractionVersion;delete e.taskInstance;delete e.knowledgeItems;delete e.solutionInstances;
    e.knowledge='管理员自定义的知识说明';e.solutionA='旧稿人工修订的解法过程，来源尚未记录。';old.workspace='semantic';old.integration.selected=e.id;
    await page.evaluate(value=>localStorage.setItem('deermind-m1-import-v1',JSON.stringify(value)),before.imports);await page.reload();
    await expect(page.getByText(/旧稿已按 KC/)).toBeVisible();const converted=await entry('MAT-GROUPS');
    assert.equal(JSON.stringify(converted.bindings),references);assert.equal(JSON.stringify((await state()).domain),domain);assert.ok(converted.knowledgeItems.some(k=>k.meaning===e.knowledge));
    const unknown=converted.solutionInstances.find(s=>s.key==='methodA');assert.equal(unknown.working,e.solutionA);assert.equal(unknown.origin,'来源待确认');
    await btn('确认本项提取结果').click();await expect(page.getByRole('alert')).toContainText('来源待核对');
    await tab('解法 SolutionInstance').click();await btn('核对解法 '+unknown.id).click();await page.getByLabel('核实后的来源',{exact:true}).selectOption('系统生成');await page.getByLabel('来源说明',{exact:true}).fill('人工核实：旧稿由系统生成。');await btn('保存解法核对').click();
    assert.equal((await entry('MAT-GROUPS')).solutionInstances.find(s=>s.key==='methodA').origin,'系统生成');
    await page.setViewportSize({width:1280,height:900});assert.ok(await page.locator('.page-container').evaluate(e=>e.scrollWidth<=e.clientWidth));await shot('06-legacy');assert.deepEqual(errors,[]);assert.deepEqual(api,[]);
  });
});
