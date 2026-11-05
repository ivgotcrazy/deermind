import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir,writeFile } from 'node:fs/promises';
import { chromium,expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';
const expect=baseExpect.configure({timeout:8000});
const output=new URL('../test-results/material-flow/',import.meta.url);

test('textbook parsing, domain intake and chapter adoption form one simple workflow',async t=>{
  await mkdir(output,{recursive:true});const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1500,height:1050}});const page=await context.newPage();page.setDefaultTimeout(8000);
  const errors=[],network=[];page.on('pageerror',e=>errors.push(e.message));await context.route('**/api/**',r=>{network.push(r.request().url());return r.abort();});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=name=>page.getByRole('button',{name,exact:true});const dialog=()=>page.getByRole('dialog');
  const data=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-import-v1'))[0]);
  const domain=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')));
  const shot=async name=>{await page.locator('.page-container').evaluate(el=>el.scrollTop=0);await page.screenshot({path:new URL(name+'.png',output).pathname.replace(/^\/([A-Z]:)/,'$1'),fullPage:true});};
  const goContent=async(chapter='分数的应用')=>{const d=await data();await page.evaluate(hash=>location.hash=hash,'/textbooks?'+new URLSearchParams({source:d.id,chapter,view:'content'}));await expect(page.locator('.material-contents')).toBeVisible();};
  const reparse=async(name,prompt,adopt=true)=>{await page.getByRole('button',{name:'重新解析 '+name,exact:true}).click();await dialog().getByLabel('需要纠正什么').fill(prompt);await dialog().getByRole('button',{name:'生成解析结果',exact:true}).click();if(adopt)await dialog().getByRole('button',{name:'采用结果',exact:true}).click();};
  const intoDomain=async()=>{await page.getByRole('link',{name:/领域待入库/}).click();await expect(page.locator('.domain-intake')).toBeVisible();};
  const processRows=async()=>{
    const keys=await page.locator('.intake-list tbody tr').evaluateAll(rows=>rows.map(r=>r.dataset.element));
    for(const key of keys){
      const row=page.locator('.intake-list [data-element="'+key+'"]');
      if(await row.getByText('已保存',{exact:true}).count())continue;
      if(await row.getByRole('button',{name:'添加知识成分',exact:true}).count()){
        await row.getByRole('button',{name:'添加知识成分',exact:true}).click();await btn('确认添加').click();continue;
      }
      const question=await row.getByRole('button',{name:'关联任务模板',exact:true}).count(),kind=question?'任务':'解法';
      await row.getByRole('button',{name:'关联'+kind+'模板',exact:true}).click();
      if(!await dialog().getByRole('combobox').inputValue()){
        await btn('取消').click();await row.getByRole('button',{name:'提取'+kind+'模板',exact:true}).click();await btn('保存模板').click();
        await row.getByRole('button',{name:'关联'+kind+'模板',exact:true}).click();
      }
      await btn('确认关联').click();await expect(dialog()).toHaveCount(0);await expect(page.getByRole('status')).toContainText('已关联');
    }
  };
  const finishFirst=processRows;
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/textbooks');await btn('导入教材').click();await expect(btn('上传并开始整理')).toBeDisabled();await btn('载入四例核对样例').click();await btn('上传并开始整理').click();await expect(page.locator('.material-contents')).toBeVisible();
  const initial=await data();
  await t.test('re-parsing replaces only the chosen element after adoption; source content stays intact',async()=>{
    for(const name of ['编辑','框选出处','移动到…','检查并应用','添加内容'])await expect(btn(name)).toHaveCount(0);
    await reparse('跨页题目与两种原有解法','还原完整题目，不加入教材解法',false);
    const before=(await data()).flow.elements.find(e=>e.id==='C02-question');assert.equal(before.title,'跨页题目与两种原有解法');await dialog().getByRole('button',{name:'取消',exact:true}).click();
    await reparse('跨页题目与两种原有解法','还原完整题目，不加入教材解法');
    await btn('教材解法 1').click();await reparse('教材解法 1','这里是两种解法，请分别提取');
    await expect(page.locator('.element-table tbody tr')).toHaveCount(2);const d=await data();assert.equal(d.flow.elements.filter(e=>e.kind==='solution').length,2);assert.deepEqual(d.contentReview,initial.contentReview);
    await shot('01-parsed-solutions');
  });
  let instanceId;
  await t.test('question-only intake creates or reuses templates without creating a solution instance',async()=>{
    await btn('题目 2').click();await page.getByLabel('选择 三个兴趣小组的人数',{exact:true}).check();await btn('提交到领域').click();
    assert.equal((await domain()).instances.length,0);await intoDomain();await shot('02-domain-intake');await btn('提取任务模板').click();await btn('保存模板').click();assert.equal((await domain()).instances.length,0);await expect(page.locator('.intake-list')).toContainText('待关联');await processRows();
    const model=await domain();assert.equal(model.instances.length,1);const q=model.instances[0];instanceId=q.id;assert.equal(q.solutions.length,0);assert.equal(q.reviewContent.filter(p=>p.role==='solution').length,0);assert.equal(model.tasks.find(t=>t.id===q.taskId).methods.length,0);assert.equal(model.methods.length,0);assert.equal(model.knowledge.length,0);assert.equal(q.checkedSignature,'');
    await page.getByRole('link',{name:'返回教材章节 →',exact:true}).click();await expect(page.locator('.chapter-links tbody tr')).toHaveCount(0);
    await expect(btn('保存章节关联')).toHaveCount(0);await expect(page.getByRole('combobox')).toHaveCount(0);
    await btn('添加关联').click();await dialog().getByLabel('任务模板',{exact:true}).selectOption(q.taskId);await btn('保存').click();await expect(dialog().getByRole('alert')).toContainText('至少选择一个');await btn('取消').click();
    assert.equal((await data()).flow.links['分数的应用'],undefined);await page.reload();await expect(page.locator('.chapter-links tbody tr')).toHaveCount(0);
  });
  await t.test('later solutions reuse the same question and bind both required references',async()=>{
    await goContent();await btn('教材解法 2').click();await page.getByLabel('选择 逐层求出人数',{exact:true}).check();await page.getByLabel('选择 先合并两层比例',{exact:true}).check();await btn('提交到领域').click();await intoDomain();await finishFirst();
    const model=await domain();assert.equal(model.instances.length,1);assert.deepEqual({tasks:model.tasks.length,methods:model.methods.length,kcs:model.knowledge.length},{tasks:1,methods:2,kcs:0});const q=model.instances[0];assert.equal(q.id,instanceId);assert.equal(q.solutions.length,2);assert.equal(new Set(q.solutions.map(s=>s.id)).size,2);assert.ok(q.solutions.every(s=>s.taskInstanceId===q.id&&model.tasks.find(t=>t.id===q.taskId).methods.includes(s.methodId)));assert.equal(q.reviewContent.filter(p=>p.role==='solution').length,2);
    await expect(page.locator('.intake-list tbody tr')).toHaveCount(0);await expect(btn('待处理')).toHaveCount(0);await expect(btn('已入库')).toHaveCount(0);await shot('04-intake-complete');await page.reload();await expect(page.locator('.domain-intake')).toBeVisible();assert.equal((await domain()).instances[0].solutions.length,2);
  });
  await t.test('chapter links are read-only and add, edit, unlink save independently with no phantom suggestions',async()=>{
    await page.getByRole('link',{name:'返回教材章节 →',exact:true}).click();
    const model=await domain(),taskId=model.instances[0].taskId;
    const main=page.locator('.chapter-workspace'),table=page.locator('.chapter-links'),nav=page.locator('.chapter-nav');
    const add=async()=>{await btn('添加关联').click();await dialog().getByLabel('任务模板',{exact:true}).selectOption(taskId);};
    const currentLinks=async()=> (await data()).flow.links['分数的应用'];
    await expect(table.locator('tbody tr')).toHaveCount(0);await expect(nav.locator('button.active')).toContainText('0 项任务已关联');
    await expect(main.getByRole('combobox')).toHaveCount(0);await expect(btn('保存章节关联')).toHaveCount(0);await expect(btn('不关联')).toHaveCount(0);
    assert.ok(await btn('添加关联').evaluate(el=>el.classList.contains('primary')));
    await btn('添加关联').click();await btn('保存').click();await expect(dialog().getByRole('alert')).toContainText('请选择任务模板');await btn('取消').click();
    await add();await expect(dialog().getByLabel('本章采用 逐层求部分量')).toBeChecked();await expect(dialog().getByLabel('本章采用 合并两层比例')).toBeChecked();
    await shot('10-add-chapter-link');await btn('取消').click();assert.equal(await currentLinks(),undefined);await expect(table.locator('tbody tr')).toHaveCount(0);
    await add();await btn('保存').click();await expect(dialog()).toHaveCount(0);await expect(page.getByRole('status')).toContainText('本章关联已保存');await expect(nav.locator('button.active')).toContainText('1 项任务已关联');
    await expect(table.getByRole('checkbox')).toHaveCount(0);await expect(table.getByRole('combobox')).toHaveCount(0);await expect(table.locator('.method-list li')).toHaveCount(2);
    const saved=await currentLinks();assert.deepEqual(Object.keys(saved[0]).sort(),['methodIds','taskId']);await page.reload();assert.deepEqual(await currentLinks(),saved);await expect(table.locator('tbody tr')).toHaveCount(1);
    await btn('添加关联').click();await expect(dialog().locator('option[value="'+taskId+'"]')).toHaveCount(0);await btn('取消').click();
    await table.getByRole('button',{name:'编辑',exact:true}).click();await expect(dialog().getByRole('combobox')).toHaveCount(0);await dialog().getByLabel('本章采用 合并两层比例').uncheck();await shot('11-edit-chapter-link');await btn('取消').click();assert.deepEqual(await currentLinks(),saved);await expect(table.locator('.method-list li')).toHaveCount(2);
    await table.getByRole('button',{name:'编辑',exact:true}).click();await dialog().getByLabel('本章采用 逐层求部分量').uncheck();await dialog().getByLabel('本章采用 合并两层比例').uncheck();await btn('保存').click();await expect(dialog().getByRole('alert')).toContainText('至少选择一个');assert.deepEqual(await currentLinks(),saved);
    await dialog().getByLabel('本章采用 逐层求部分量').check();await btn('保存').click();await expect(table.locator('.method-list li')).toHaveCount(1);await expect(table.locator('.method-list')).toContainText('逐层求部分量');assert.equal((await currentLinks())[0].methodIds.length,1);
    await page.reload();await expect(table.locator('.method-list li')).toHaveCount(1);assert.deepEqual(await domain(),model);
    await table.getByRole('button',{name:'取消关联',exact:true}).click();await expect(table.locator('tbody tr')).toHaveCount(0);assert.equal(await currentLinks(),undefined);assert.deepEqual(await domain(),model);await expect(nav.locator('button.active')).toContainText('0 项任务已关联');
    await page.reload();await expect(table.locator('tbody tr')).toHaveCount(0);await add();await btn('保存').click();await expect(table.locator('tbody tr')).toHaveCount(1);
    await nav.getByRole('button',{name:/统计图/}).click();await expect(table.locator('tbody tr')).toHaveCount(0);await nav.getByRole('button',{name:/分数的应用/}).click();await expect(table.locator('tbody tr')).toHaveCount(1);
    await page.setViewportSize({width:1280,height:900});assert.ok(await main.evaluate(el=>el.scrollWidth<=el.clientWidth));await shot('03-chapter-links');await page.setViewportSize({width:1500,height:1050});
  });
  await t.test('KC intake reuses knowledge and does not create a direct chapter-to-KC relationship',async()=>{
    await goContent();await btn('知识 1').click();await page.getByLabel('选择 除以非零数等于乘其倒数',{exact:true}).check();await btn('提交到领域').click();await intoDomain();await finishFirst();
    const d=await data(),r=d.flow.requests.find(r=>r.rootId==='K-RECIP');assert.equal(r.status,'done');assert.ok((await domain()).knowledge.some(k=>k.id===r.result['K-RECIP'].objectId));assert.equal(r.result['K-RECIP'].templateId,'');assert.deepEqual(Object.keys(d.flow.links['分数的应用'][0]).sort(),['methodIds','taskId']);
  });
  await t.test('chart re-parsing preserves rendering, geometry and wrong worked examples remain source data',async()=>{
    await goContent('统计图');await expect(page.getByLabel('选择 三种统计图与教学提示')).toBeDisabled();await reparse('三种统计图与教学提示','补齐原题里的三张统计图',false);await expect(dialog().locator('svg')).toHaveCount(3);await shot('05-reparse-chart');await dialog().getByRole('button',{name:'采用结果',exact:true}).click();await page.getByLabel('选择 三种统计图与教学提示').check();await btn('提交到领域').click();await intoDomain();await finishFirst();
    const model=await domain();const q=model.instances.find(i=>i.reviewContent?.some(p=>p.blocks.some(b=>b.type==='chart')));assert.equal(q.reviewContent.flatMap(p=>p.blocks).filter(b=>b.type==='chart').length,3);
    await goContent('圆');await page.getByRole('button',{name:'六种平面图形和原图标记',exact:true}).click();await expect(dialog().locator('svg circle[fill="#c62a7c"]')).toHaveCount(6);await dialog().getByRole('button',{name:'取消',exact:true}).click();
    await goContent();await reparse('保留原题中的错误演算','只修正格式，保留原题故意写错的算式');const e=(await data()).flow.elements.find(e=>e.id==='C03-question');assert.ok(e.blocks.some(b=>b.type==='formula'&&b.lines.some(l=>l.includes('7/32'))));
  });
  await t.test('re-parsing a pending item expires its request and a new submission refreshes the source',async()=>{
    await page.getByLabel('选择 保留原题中的错误演算').check();await btn('提交到领域').click();const d=await data(),r=d.flow.requests.find(r=>r.rootId==='C03-question'&&r.status==='pending');assert.ok(r);
    await reparse('保留原题中的错误演算','再次按原文解析');assert.equal((await data()).flow.requests.find(x=>x.id===r.id).status,'outdated');await page.getByLabel('选择 保留原题中的错误演算').check();await btn('提交到领域').click();await intoDomain();await finishFirst();assert.equal((await data()).flow.requests.filter(r=>r.rootId==='C03-question'&&r.status==='pending').length,0);
  });
  await goContent();await page.setViewportSize({width:1280,height:900});assert.ok(await page.locator('.page-container').evaluate(el=>el.scrollWidth<=el.clientWidth));await shot('06-textbook-overview');assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
  await t.test('question with separately selected solutions is grouped once and imported together',async()=>{
    await btn('← 返回教材列表').click();await btn('导入教材').click();await btn('载入四例核对样例').click();await btn('上传并开始整理').click();await expect(page.locator('.material-contents')).toBeVisible();
    await reparse('跨页题目与两种原有解法','还原题目');await btn('教材解法 1').click();await reparse('教材解法 1','分别提取两种解法');
    await page.getByLabel('选择 逐层求出人数').check();await btn('题目 2').click();await page.getByLabel('选择 三个兴趣小组的人数').check();await btn('提交到领域').click();
    await btn('教材解法 2').click();await page.getByLabel('选择 先合并两层比例').check();await btn('提交到领域').click();
    const d=await data();assert.equal(d.flow.requests.filter(r=>r.status==='pending').length,1);assert.equal(d.flow.requests[0].elements.length,3);await intoDomain();await expect(btn('处理')).toHaveCount(0);
    const solution2=d.flow.requests[0].elements.find(e=>e.recipe==='ST-COMBINE').id;
    const row=id=>page.locator('.intake-list [data-element="'+id+'"]');
    await expect(page.locator('.intake-list').getByRole('button',{name:'关联解法模板',exact:true}).first()).toBeDisabled();
    await expect(page.locator('.domain-tabs button.active span')).toHaveText('3');await shot('07-row-actions');
    const beforeParent=await domain();await row('C02-question').getByRole('button',{name:'删除',exact:true}).click();await expect(dialog()).toContainText('2 条待处理解法');await btn('确认删除').click();await expect(page.locator('.intake-list tbody tr')).toHaveCount(0);assert.deepEqual((await data()).flow.elements,d.flow.elements);assert.deepEqual(await domain(),beforeParent);await expect(dialog()).toHaveCount(0);
    await goContent();await page.getByLabel('选择 三个兴趣小组的人数').check();await btn('教材解法 2').click();await page.getByLabel('选择 逐层求出人数').check();await page.getByLabel('选择 先合并两层比例').check();await btn('提交到领域').click();await intoDomain();await expect(btn('处理')).toHaveCount(0);
    const beforeDelete=await domain();await row(solution2).getByRole('button',{name:'删除',exact:true}).click();await btn('确认删除').click();await expect(row(solution2)).toHaveCount(0);
    assert.deepEqual((await data()).flow.elements,d.flow.elements);assert.deepEqual(await domain(),beforeDelete);await expect(dialog()).toHaveCount(0);
    await goContent();await btn('教材解法 2').click();await page.getByLabel('选择 先合并两层比例').check();await btn('提交到领域').click();await intoDomain();await expect(btn('处理')).toHaveCount(0);await expect(row(solution2)).toBeVisible();
    await btn('提取任务模板').click();await shot('08-extract-template');await btn('保存模板').click();
    assert.equal((await domain()).instances.filter(i=>i.domainId===d.book.domainId).length,0);await expect(row('C02-question')).toContainText('待关联');
    await expect(dialog()).toHaveCount(0);await page.reload();await expect(btn('处理')).toHaveCount(0);await expect(row('C02-question')).toContainText('已提取');
    await btn('关联任务模板').click();await btn('确认关联').click();await expect(row('C02-question')).toContainText('已关联');
    await expect(row('C02-question').getByRole('button',{name:'删除',exact:true})).toHaveCount(0);
    await expect(page.locator('.domain-tabs button.active span')).toHaveText('2');await shot('09-partial-completion');await expect(dialog()).toHaveCount(0);await page.reload();await expect(btn('处理')).toHaveCount(0);await expect(row('C02-question')).toContainText('已关联');
    await processRows();const m=await domain(),q=m.instances.filter(i=>i.domainId===d.book.domainId);assert.equal(q.length,1);assert.equal(q[0].solutions.length,2);assert.ok(q[0].solutions.every(s=>s.taskInstanceId===q[0].id));
    assert.equal(m.tasks.filter(t=>t.domainId===d.book.domainId).length,1);assert.equal(m.methods.filter(t=>t.domainId===d.book.domainId).length,2);
    await goContent();await btn('知识 1').click();await page.getByLabel('选择 除以非零数等于乘其倒数').check();await btn('提交到领域').click();await intoDomain();await expect(btn('处理')).toHaveCount(0);
    const beforeKc=await domain();await btn('删除').click();await btn('确认删除').click();await expect(page.getByText('当前没有待入库内容。',{exact:true})).toBeVisible();assert.deepEqual(await domain(),beforeKc);await expect(dialog()).toHaveCount(0);
    await goContent();await reparse('保留原题中的错误演算','保留原题');await page.getByLabel('选择 保留原题中的错误演算').check();await btn('提交到领域').click();await intoDomain();await expect(btn('处理')).toHaveCount(0);
    await btn('提取任务模板').click();await btn('保存模板').click();const beforeQuestion=await domain();await btn('删除').click();await btn('确认删除').click();assert.deepEqual(await domain(),beforeQuestion);await expect(dialog()).toHaveCount(0);await expect(btn('处理')).toHaveCount(0);
  });
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
  await writeFile(new URL('review.json',output),JSON.stringify({status:'passed',modelCalls:0,cases:['question-only','later-solutions','knowledge','charts','geometry','wrong-example','reparse-stale-request','extract-without-associating','partial-completion-reload','remove-knowledge-question-solution','chapter-link-add-edit-cancel-unlink-reload'],errors},null,2));
});
