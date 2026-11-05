import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium, expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';
const expect=baseExpect.configure({timeout:10000});
const output=fileURLToPath(new URL('../test-results/visual-ownership/',import.meta.url));

test('visuals stay with their content and teaching aids never enter question previews',async t=>{
  await mkdir(output,{recursive:true});const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch({headless:true}),context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
  const page=await context.newPage();page.setDefaultTimeout(10000);const errors=[],api=[];
  page.on('pageerror',e=>errors.push(e.message));await context.route('**/api/**',r=>{api.push(r.request().url());return r.abort();});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=name=>page.getByRole('button',{name,exact:true});
  const state=()=>page.evaluate(()=>({imports:JSON.parse(localStorage.getItem('deermind-m1-import-v1')||'[]'),domain:JSON.parse(localStorage.getItem('deermind-m1-domain-v1')||'{}')}));
  const entry=async id=>(await state()).imports[0].integration.entries.find(e=>e.id===id);
  const tab=prefix=>page.getByRole('navigation',{name:'提取对象类型'}).getByRole('button',{name:new RegExp('^'+prefix)});
  const select=async name=>{await btn('内容提取').click();await page.locator('.integration-entry').filter({hasText:name}).click();};
  const shot=async name=>{await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:output+name+'.png',animations:'disabled'});};
  const confirm=async()=>{await btn('确认本项提取结果').click();await btn('匹配或补建模板').click();};

  await t.test('original question excludes analysis, solution and knowledge illustrations',async()=>{
    await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/textbooks');await btn('导入教材').click();await page.getByText('Mock处理场景',{exact:true}).click();await btn('空领域新建').click();await btn('上传并开始整理').click();
    await expect(btn('预览原题')).toBeVisible();await expect(page.getByText('题目中的图表信息',{exact:true})).toHaveCount(0);
    await btn('预览原题').click();const preview=page.getByTestId('extracted-task-preview');await expect(preview).toContainText('气象小组12人');await expect(preview.locator('figure')).toHaveCount(0);await expect(preview).not.toContainText('4人');await expect(preview).not.toContainText('3人');await shot('01-question');await btn('关闭预览').click();
    await page.locator('.teaching-visuals summary').click();await expect(page.getByRole('figure',{name:'两层比例关系分析图',exact:true})).toBeVisible();await shot('02-teaching');await page.locator('.teaching-visuals summary').click();
    await tab('解法 SolutionInstance').click();const e=await entry('MAT-GROUPS');await btn('核对解法 '+e.solutionInstances[0].id).click();await expect(page.getByRole('dialog')).toContainText('摄影 4人');await expect(page.getByRole('dialog')).toContainText('不是原书图形');await shot('03-solution');await btn('取消').click();
    await tab('知识 KC').click();await btn('编辑提取知识 base').click();await expect(page.getByRole('dialog')).toContainText('参照整体 A');await shot('04-knowledge');await btn('取消').click();
  });

  await t.test('saved instances and knowledge retain their own visuals, student preview retains no hints',async()=>{
    await confirm();await btn('补齐缺少的模板与知识（mock）').click();await btn('检查并保存实例（mock）').click();await btn('保存本项映射').click();await expect(page.getByRole('alert')).toHaveCount(0);
    const s=await state(),e=await entry('MAT-GROUPS'),q=s.domain.instances[0];assert.deepEqual(q.visuals,[]);assert.equal(q.solutions[0].visuals[0].title,'先求摄影人数，再求航模人数');assert.equal(s.domain.knowledge.find(k=>k.id===e.bindings.base.id).visuals[0].title,'分率必须对应一个参照整体');
    await btn('查看已保存题目').click();await expect(page.getByRole('dialog')).toContainText('摄影 4人');await btn('预览学生题面').click();await expect(page.getByTestId('student-question').locator('figure')).toHaveCount(0);await expect(page.getByTestId('student-question')).not.toContainText('摄影 4人');await btn('关闭对话框').click();await btn('← 返回本项融合').click();
    await btn('查看对象 base').click();await expect(page.getByRole('figure',{name:'分率必须对应一个参照整体',exact:true})).toBeVisible();await btn('← 返回本项融合').click();
  });

  await t.test('cancel preserves ownership; an aid can move to the specific solution without entering the task',async()=>{
    await select('三个兴趣小组');await page.locator('.teaching-visuals summary').click();await btn('编辑图表 两层比例关系分析图').click();const e=await entry('MAT-GROUPS'),solution=e.solutionInstances[0];
    await page.getByLabel('所属内容',{exact:true}).selectOption(solution.id);await btn('取消').click();assert.equal((await entry('MAT-GROUPS')).teachingVisuals.length,1);
    await btn('编辑图表 两层比例关系分析图').click();await page.getByLabel('所属内容',{exact:true}).selectOption(solution.id);await btn('保存图表').click();await page.reload();
    const moved=await entry('MAT-GROUPS');assert.equal(moved.teachingVisuals.length,0);assert.equal(moved.solutionInstances[0].visuals.length,2);assert.deepEqual(moved.taskInstance.visuals,[]);
    await confirm();await btn('保存本项映射').click();await expect(page.getByRole('alert')).toContainText('具体解法已有变化');await btn('检查并保存实例（mock）').click();await btn('保存本项映射').click();await expect(page.getByRole('alert')).toHaveCount(0);
  });

  await t.test('a real question table requires explicit placement and survives save and preview',async()=>{
    await select('三个兴趣小组');await btn('添加题面图表').click();await page.getByLabel('图表名称',{exact:true}).fill('原题已知数量表');await page.getByLabel('表达的内容',{exact:true}).fill('仅整理题目已给定的三个条件。');await page.getByLabel('来源说明',{exact:true}).fill('人工整理原题条件；不补入中间量或答案。');await page.getByLabel('表达形式',{exact:true}).selectOption('table');
    await page.getByLabel('图表表头 1',{exact:true}).fill('条件');await page.getByLabel('图表表头 2',{exact:true}).fill('数值');await page.getByLabel('图表数据 1 1',{exact:true}).fill('气象小组人数');await page.getByLabel('图表数据 1 2',{exact:true}).fill('12');
    await btn('保存图表').click();await expect(page.getByRole('dialog').getByRole('alert')).toContainText('请确认');assert.deepEqual((await entry('MAT-GROUPS')).taskInstance.visuals,[]);
    await page.getByLabel('已核对：这是题面内容，没有额外解题提示',{exact:true}).check();await btn('保存图表').click();
    await btn('预览原题').click();await expect(page.getByTestId('extracted-task-preview')).toContainText('原题已知数量表');await expect(page.getByTestId('extracted-task-preview')).not.toContainText('摄影 4人');await btn('关闭预览').click();
    await confirm();await btn('保存本项映射').click();await expect(page.getByRole('alert')).toContainText('题面图表已变化');await btn('检查并保存实例（mock）').click();await btn('保存本项映射').click();await expect(page.getByRole('alert')).toHaveCount(0);await btn('查看已保存题目').click();await btn('预览学生题面').click();await expect(page.getByTestId('student-question')).toContainText('原题已知数量表');await expect(page.getByTestId('student-question')).not.toContainText('两层比例关系分析图');await shot('05-saved-preview');await btn('关闭对话框').click();await btn('← 返回本项融合').click();
  });

  await t.test('all source tables and empty answer cells are retained inside the task',async()=>{
    await select('整理与比较人口数据');await btn('预览原题').click();await expect(page.getByTestId('extracted-task-preview').getByRole('table')).toHaveCount(2);await expect(page.getByTestId('extracted-task-preview')).toContainText('264018766');await expect(page.getByTestId('extracted-task-preview')).toContainText('17.95');await shot('06-tables');await btn('关闭预览').click();
    await select('设计研究方案');await btn('预览原题').click();const table=page.getByTestId('extracted-task-preview').getByRole('table');await expect(table).toContainText('数据从哪里获取');assert.deepEqual(await table.locator('tbody td').allTextContents(),['','','']);await btn('关闭预览').click();
  });

  await t.test('ambiguous legacy diagrams are retained for classification and do not overwrite domain objects',async()=>{
    const s=await state(),draft=s.imports[0],e=draft.integration.entries.find(x=>x.id==='MAT-GROUPS'),originalDomain=JSON.stringify(s.domain);
    delete e.visualsVersion;e.diagram={base:'旧稿整体',middle:'自定义中间量',end:'旧稿结果',value:'10',r:'1/5',s:'1/2'};e.visualMeaning='用户原有图示，含中间分析，请保留。';draft.integration.selected=e.id;draft.workspace='semantic';
    await page.evaluate(value=>localStorage.setItem('deermind-m1-import-v1',JSON.stringify(value)),s.imports);await page.reload();
    await expect(page.getByText('旧稿图表待核对归属',{exact:true})).toBeVisible();assert.equal(JSON.stringify((await state()).domain),originalDomain);const migrated=await entry('MAT-GROUPS');assert.equal(migrated.pendingVisuals.length,1);assert.equal(migrated.taskInstance.visuals.length,1);
    await btn('确认本项提取结果').click();await expect(page.getByRole('alert')).toContainText('未归属的图表');await btn('预览原题').click();await expect(page.getByTestId('extracted-task-preview')).not.toContainText('自定义中间量');await btn('关闭预览').click();
    await btn('编辑图表 两层比例关系分析图').click();await page.getByLabel('所属内容',{exact:true}).selectOption('teaching');await page.getByLabel('图表来源',{exact:true}).selectOption('人工整理');await btn('保存图表').click();await expect(page.getByText('旧稿图表待核对归属',{exact:true})).toHaveCount(0);await page.reload();assert.equal((await entry('MAT-GROUPS')).teachingVisuals.length,1);
    await page.setViewportSize({width:1280,height:900});assert.ok(await page.locator('.page-container').evaluate(el=>el.scrollWidth<=el.clientWidth));assert.deepEqual(errors,[]);assert.deepEqual(api,[]);
  });
});
