import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium, expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../test-results/textbook-fusion/',import.meta.url));
const expect=baseExpect.configure({timeout:10000});
test('textbook semantic import reuses or adds domain objects and exposes preparation boundaries',async t=>{
  await mkdir(output,{recursive:true});
  const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
  const page=await context.newPage(),errors=[],requests=[];page.setDefaultTimeout(10000);
  page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/api/**',route=>{requests.push(route.request().url());return route.abort();});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const button=name=>page.getByRole('button',{name,exact:true});
  const data=()=>page.evaluate(()=>({domain:JSON.parse(localStorage.getItem('deermind-m1-domain-v1')||'{}'),imports:JSON.parse(localStorage.getItem('deermind-m1-import-v1')||'[]')}));
  const counts=(d,id)=>['tasks','methods','knowledge','instances'].map(k=>d[k].filter(o=>o.domainId===id).length);
  const shot=async name=>{await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:output+name+'.png',animations:'disabled'});};
  const openImport=async()=>{await page.goto(base+'/admin/#/textbooks');await button('导入教材').click();};
  const fixture=async label=>{await openImport();await page.getByText('Mock处理场景',{exact:true}).click();await button(label).click();await button('上传并开始整理').click();await expect(button('确认本项提取结果')).toBeVisible();};
  const confirm=async()=>{await button('确认本项提取结果').click();await button('匹配或补建模板').click();};
  let retained,domainId,existingSnapshot;

  await t.test('a valid domain is required and can be created without leaving the import',async()=>{
    await openImport();await button('载入真实教材书页').click();
    await expect(button('上传并开始整理')).toBeDisabled();
    await expect(page.getByText('请先选择所属领域，再开始导入。',{exact:true})).toBeVisible();
    await button('新建领域').click();await page.getByLabel('领域名称',{exact:true}).fill('小学数学 · 手动创建');
    await button('取消').click();assert.equal((await data()).domain.domains?.length||0,0);
    await button('新建领域').click();await page.getByLabel('领域名称',{exact:true}).fill('小学数学 · 手动创建');
    await page.getByLabel('覆盖范围',{exact:true}).fill('小学数学');await button('创建并选用').click();
    const state=await data();domainId=state.domain.domains[0].id;retained=state.imports[0].id;
    await expect(page.getByLabel('所属领域',{exact:true})).toHaveValue(domainId);
    await button('上传并开始整理').click();await expect(button('确认本项提取结果')).toBeVisible();
    await expect(page.getByRole('region',{name:'题面内容'}).locator('figure')).toHaveCount(0);
    await page.locator('.teaching-visuals summary').click();
    await expect(page.getByLabel('两层比例关系分析图',{exact:true})).toContainText('1/3');
    await page.locator('.teaching-visuals summary').click();
    await shot('01-semantic');
    await button('查看原页并核对').click();await page.locator('.source-paper img').evaluate(i=>i.decode());
    await expect(button('49 页')).toBeVisible();await button('内容提取').click();
    await confirm();
    assert.deepEqual(counts((await data()).domain,domainId),[0,0,0,0]);
  });

  await t.test('new candidate cancellation and rejected checks create no phantom objects',async()=>{
    await button('新建对象 base').click();await expect(page.getByLabel('知识名称',{exact:true})).toBeVisible();
    await button('← 返回本项融合').click();assert.deepEqual(counts((await data()).domain,domainId),[0,0,0,0]);
    await button('新建对象 base').click();await button('内容提取').click();
    await expect(button('编辑题目提取')).toBeVisible();await button('匹配或补建模板').click();
    await button('新建对象 base').click();await page.getByLabel('示例与边界说明',{exact:true}).fill('人工核对：两个分率的整体不同。');
    await button('保存知识').click();
    assert.deepEqual(counts((await data()).domain,domainId),[0,0,1,0]);
    await page.getByText('模拟候选检查',{exact:true}).click();await page.getByLabel('候选检查结果',{exact:true}).selectOption('fail');
    await button('补齐缺少的模板与知识（mock）').click();await expect(page.getByRole('alert')).toContainText('本次未新建对象');
    assert.deepEqual(counts((await data()).domain,domainId),[0,0,1,0]);
    await page.getByLabel('候选检查结果',{exact:true}).selectOption('pass');
    await button('补齐缺少的模板与知识（mock）').click();
    await expect(page.getByRole('alert')).toHaveCount(0);
    assert.deepEqual(counts((await data()).domain,domainId),[1,2,3,0]);
    assert.equal((await data()).domain.knowledge.find(k=>k.domainId===domainId&&k.name==='分率的参照整体').example,'人工核对：两个分率的整体不同。');
    await button('补齐缺少的模板与知识（mock）').click();assert.deepEqual(counts((await data()).domain,domainId),[1,2,3,0]);
    await shot('02-fusion');
  });

  await t.test('chapter method selection derives its KC without changing the domain Task',async()=>{
    await expect(page.getByRole('table',{name:'本教材汇总知识'}).locator('tbody tr')).toHaveCount(3);
    await page.getByLabel('先合并比例，再求最终量',{exact:false}).uncheck();
    await expect(page.getByRole('table',{name:'本教材汇总知识'}).locator('tbody tr')).toHaveCount(2);
    assert.equal((await data()).domain.tasks.find(x=>x.domainId===domainId).methods.length,2);
    await button('检查并保存实例（mock）').click();
    await button('保存本项映射').click();await expect(page.getByRole('alert')).toHaveCount(0);
    await page.getByRole('navigation',{name:'导入工作区'}).getByRole('button',{name:'检查并应用',exact:true}).click();
    await expect(button('模拟应用本项内容')).toBeDisabled();
    await button('准备应用条件（mock）').click();await button('载入演示配置').click();await button('采用演示配置').click();
    await button('模拟应用本项内容').click();await expect(page.getByRole('heading',{name:'本项已模拟应用',exact:true})).toBeVisible();
    await shot('03-application');
    await button('← 返回教材列表').click();
    await expect(page.locator(`[data-applied-id="${retained}"]`)).toContainText('1 项内容就绪');
    await expect(page.locator(`[data-applied-id="${retained}"]`)).toContainText('未完成整册');
    await expect(page.locator(`[data-applied-id="${retained}"]`).getByRole('button',{name:/删除/})).toHaveCount(0);
    await shot('04-books');
  });

  await t.test('source edits invalidate review and application; refresh retains the warning',async()=>{
    await page.locator(`[data-applied-id="${retained}"]`).getByRole('button').click();
    await button('内容提取').click();await button('编辑题目提取').click();
    await page.getByLabel('问题与作答要求',{exact:true}).fill('航模小组有多少人？请解释两层分率各自的整体。');
    await button('保存题目提取').click();
    await expect(button('匹配或补建模板')).toBeDisabled();
    await page.reload();await button('检查并应用').click();await expect(button('模拟应用本项内容')).toBeDisabled();
    await expect(page.getByText('已有应用记录，当前修改尚未应用',{exact:true})).toBeVisible();
    await button('← 返回教材列表').click();await expect(page.locator(`[data-applied-id="${retained}"]`)).toContainText('0 项内容就绪');
  });

  await t.test('full reuse preserves the exact existing domain definitions and instances',async()=>{
    await fixture('全部已有对象');await confirm();
    const before=await data(),d=before.imports[0].book.domainId;
    existingSnapshot=JSON.stringify(before.domain);
    assert.deepEqual(counts(before.domain,d),[1,2,3,1]);
    await button('选择已有 task').click();
    await expect(page.getByLabel('已有对象',{exact:true}).locator('option')).toHaveCount(2);
    await button('复用所选对象').click();
    await button('补齐缺少的模板与知识（mock）').click();await button('检查并保存实例（mock）').click();await button('保存本项映射').click();
    await expect(page.getByRole('alert')).toHaveCount(0);
    assert.equal(JSON.stringify((await data()).domain),existingSnapshot);
    await shot('05-reuse');
    await page.setViewportSize({width:1280,height:900});
    assert.ok(await page.locator('.page-container').evaluate(e=>e.scrollWidth<=e.clientWidth),'No desktop page overflow');
    await shot('06-desktop-1280');await page.setViewportSize({width:1440,height:1000});
  });

  await t.test('partial reuse adds only missing objects; deletion retains shared definitions',async()=>{
    await fixture('部分已有对象');await confirm();
    const before=await data(),draft=before.imports[0],d=draft.book.domainId;
    const knowledge=JSON.stringify(before.domain.knowledge.filter(k=>k.domainId===d));
    assert.deepEqual(counts(before.domain,d),[0,0,3,0]);
    await button('补齐缺少的模板与知识（mock）').click();await button('检查并保存实例（mock）').click();await button('保存本项映射').click();
    await expect(page.getByRole('alert')).toHaveCount(0);
    assert.deepEqual(counts((await data()).domain,d),[1,2,3,1]);
    assert.equal(JSON.stringify((await data()).domain.knowledge.filter(k=>k.domainId===d)),knowledge);
    await button('查看已保存题目').click();await button('预览学生题面').click();
    await expect(page.getByTestId('student-question')).not.toContainText('3人');
    await expect(page.getByTestId('student-question')).not.toContainText('12×1/3=4');
    await page.getByRole('dialog').getByRole('button',{name:'关闭对话框',exact:true}).click();await button('← 返回本项融合').click();
    await button('← 返回教材列表').click();
    await page.locator(`[data-import-id="${draft.id}"]`).getByRole('button',{name:/删除/}).click();
    await expect(page.getByRole('dialog')).toContainText('公共定义和题目保留');await button('确认删除').click();
    assert.ok(!(await data()).imports.some(x=>x.id===draft.id));assert.deepEqual(counts((await data()).domain,d),[1,2,3,1]);
  });

  await t.test('unprepared material stays unprepared and no backend is called',async()=>{
    await fixture('空领域新建');
    await page.locator('.integration-entry').filter({hasText:'同一组数据的三种统计图'}).click();
    await expect(page.getByText('统计图的数据、单位和图例仍需核对补齐。',{exact:false})).toBeVisible();
    await button('检查并应用').click();await expect(button('模拟应用本项内容')).toBeDisabled();
    await expect(page.getByText('尚未选择本项 TaskTemplate',{exact:true})).toBeVisible();
    assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  });
  await t.test('book and domain columns stay separate and combined filters cover both lists',async()=>{
    await button('← 返回教材列表').click();
    await expect(page.getByRole('columnheader',{name:'教材',exact:true})).toHaveCount(2);
    await expect(page.getByRole('columnheader',{name:'所属领域',exact:true})).toHaveCount(2);
    const state=await data(),pending=state.imports.find(d=>d.id!==retained&&!d.integration?.applications.length);
    await page.getByLabel('按领域查找',{exact:true}).selectOption(domainId);
    await expect(page.locator('[data-applied-id]')).toHaveCount(1);
    await expect(page.locator('[data-import-id]')).toHaveCount(0);
    await page.getByLabel('查找教材',{exact:true}).fill('不存在的教材名称');
    await expect(page.locator('[data-applied-id],[data-import-id]')).toHaveCount(0);
    await page.getByLabel('查找教材',{exact:true}).fill('');
    await page.getByLabel('按领域查找',{exact:true}).selectOption(pending.book.domainId);
    await expect(page.locator('[data-applied-id]')).toHaveCount(0);
    await expect(page.locator('[data-import-id]')).toHaveCount(1);
    await page.getByLabel('按领域查找',{exact:true}).selectOption('');
    await expect(page.locator('[data-applied-id],[data-import-id]')).toHaveCount(state.imports.length);
    await page.setViewportSize({width:1280,height:900});
    assert.ok(await page.locator('.page-container').evaluate(e=>e.scrollWidth<=e.clientWidth));
    await shot('07-domain-filter');assert.deepEqual(errors,[]);
  });
});
