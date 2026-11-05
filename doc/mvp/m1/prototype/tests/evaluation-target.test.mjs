import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium, expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

const expect=baseExpect.configure({timeout:8000});
test('M1 Domain Claim and textbook target management',async t=>{
  const server=createPreviewServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
  const page=await context.newPage();page.setDefaultTimeout(8000);
  const errors=[],api=[],screens=[];page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/api/**',r=>{api.push(r.request().url());return r.abort();});
  t.after(async()=>{await browser.close();await new Promise(resolve=>server.close(resolve));});
  const output=fileURLToPath(new URL('../test-results/evaluation-target/',import.meta.url));await mkdir(output,{recursive:true});
  const go=path=>page.goto(base+'/admin/#/'+path);
  const btn=name=>page.getByRole('button',{name,exact:true});
  const label=name=>page.getByLabel(name,{exact:true});
  const state=()=>page.evaluate(()=>({evaluation:JSON.parse(localStorage.getItem('deermind-m1-evaluation-v1')||'{}'),domain:JSON.parse(localStorage.getItem('deermind-m1-domain-v1')||'{}'),imports:JSON.parse(localStorage.getItem('deermind-m1-import-v1')||'[]')}));
  const shot=async name=>{await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:output+name+'.png',animations:'disabled'});screens.push(name);};
  let seedTarget,seedClaim,seedBook,task,manualClaim,newTarget;
  await t.test('Claim creation is independent of textbook; incomplete definitions stay pending',async()=>{
    await go('domain');await btn('新建领域').click();await label('领域名称').fill('无教材领域');await label('覆盖范围').fill('人工定义的学习任务');await btn('创建并进入').click();
    const domainId=(await state()).domain.domains[0].id;
    await btn('新建任务模板').click();await label('任务名称').fill('独立领域任务');await label('任务目标').fill('完成指定工作');await label('学习者承担的工作').fill('自行完成并说明');await btn('创建任务模板').click();
    const taskId=(await state()).domain.tasks[0].id;
    await go('evaluation');await btn('新建 Claim').click();await label('所属领域').selectOption(domainId);await label('关联 Task').selectOption(taskId);await label('Claim 名称').fill('不依附教材的 Claim');await btn('创建 Claim').click();
    await expect(page.getByRole('heading',{name:'不依附教材的 Claim',exact:true})).toBeVisible();
    await expect(page.getByText(/项定义待补充或核对/)).toBeVisible();
    const data=await state();manualClaim=data.evaluation.claims[0];assert.equal(data.imports.length,0);assert.equal(manualClaim.aspects.length,4);assert.equal(manualClaim.taskId,taskId);assert.equal('bookId' in manualClaim,false);
    await btn('编辑基本信息').click();await label('Claim 名称').fill('取消的修改');await btn('取消').click();await page.reload();await expect(page.getByRole('heading',{name:'不依附教材的 Claim',exact:true})).toBeVisible();
  });
  await t.test('opt-in example connects Domain, one multidimensional Claim, textbook chapter and target',async()=>{
    await go('evaluation');await btn('打开四分之一样例').click();await expect(page.getByRole('heading',{name:'比例增加任务的理解与求解',exact:true})).toBeVisible();
    const data=await state();seedTarget=data.evaluation.targets.find(t=>t.id==='TARGET-M1-QUARTER-DEMO');seedClaim=data.evaluation.claims.find(c=>c.id===seedTarget.requirements[0].claimId);seedBook=data.imports.find(d=>d.book.id===seedTarget.bookId);task=data.domain.tasks.find(t=>t.id===seedClaim.taskId);
    assert.equal(data.evaluation.claims.length,2);assert.equal(seedClaim.aspects.length,4);assert.equal(seedClaim.taskVersion,task.version);assert.equal(seedTarget.requirements[0].standards.length,4);assert.ok(seedTarget.requirements[0].standards.find(s=>s.aspectId==='transfer').text.includes('表格'));assert.ok(seedTarget.requirements[0].standards.find(s=>s.aspectId==='retention').text.includes('7×24'));
    await shot('01-claim-definition');
    await go('targets?id='+seedTarget.id);await expect(page.getByRole('heading',{name:seedTarget.name,exact:true})).toBeVisible();await expect(page.locator('.preparation')).toHaveCount(0);await shot('02-target-requirements');
    const before=await state();await go('evaluation');await btn('打开四分之一样例').click();const after=await state();assert.deepEqual(after.domain,before.domain);assert.deepEqual(after.imports,before.imports);assert.equal(after.evaluation.targets.length,1);
  });
  await t.test('a second target reuses the Claim; selection and standards do not mutate its definition',async()=>{
    await go('targets');await btn('新建学习目标').click();await label('目标名称').fill('本周四分之一学习要求');await label('教材').selectOption(seedTarget.bookId);await label(seedTarget.chapters[0]).check();await btn('创建学习目标').click();
    newTarget=(await state()).evaluation.targets.find(t=>t.name==='本周四分之一学习要求');
    await btn('添加学习要求').click();await expect(label('选用 Claim').locator('option[value="'+manualClaim.id+'"]')).toHaveCount(0);await label('选用 Claim').selectOption(seedClaim.id);
    await label('学习要求名称').fill('自己求解并说明四分之一的参照量');await label('具体任务范围').fill(seedTarget.requirements[0].scope);
    for(const a of seedClaim.aspects)await label(a.name+'达标标准').fill(seedTarget.requirements[0].standards.find(s=>s.aspectId===a.id).text);
    await btn('保存学习要求').click();await expect(page.getByRole('alert')).toContainText('请核对范围');
    await page.getByRole('checkbox',{name:/已核对：范围在 Claim 内/}).check();await btn('保存学习要求').click();await expect(page.getByRole('dialog')).toHaveCount(0);
    const data=await state();assert.deepEqual(data.evaluation.claims.find(c=>c.id===seedClaim.id),seedClaim);assert.equal(data.evaluation.targets.find(t=>t.id===newTarget.id).requirements.length,1);
    await page.reload();await expect(page.getByRole('heading',{name:'自己求解并说明四分之一的参照量',exact:true})).toBeVisible();await shot('03-reused-claim-target');
    await btn('添加学习要求').click();await label('选用 Claim').selectOption(seedClaim.id);await label('学习要求名称').fill('另一个任务子范围');await label('具体任务范围').fill('增加比例 r=1/2；原量为正，离散数量满足整量条件。');
    for(const a of seedClaim.aspects)await label(a.name+'达标标准').fill(seedTarget.requirements[0].standards.find(s=>s.aspectId===a.id).text.replaceAll('四分之一','二分之一'));
    await page.getByRole('checkbox',{name:/已核对：范围在 Claim 内/}).check();await btn('保存学习要求').click();assert.equal((await state()).evaluation.targets.find(t=>t.id===newTarget.id).requirements.length,2);assert.deepEqual((await state()).evaluation.claims.find(c=>c.id===seedClaim.id),seedClaim);
    await page.getByRole('button',{name:'移除要求 另一个任务子范围',exact:true}).click();await btn('确认移除').click();
  });
  await t.test('aspect trimming and extension require reasons; cancel preserves original definition',async()=>{
    await go('evaluation?id='+seedClaim.id);await btn('编辑迁移').click();await label('适用于本 Claim').uncheck();await btn('保存修改').click();await expect(page.getByRole('alert')).toContainText('裁剪或扩展');await btn('取消').click();
    await btn('增加评价方面').click();await label('方面名称').fill('结果合理性检查');await btn('保存修改').click();await expect(page.getByRole('alert')).toContainText('裁剪或扩展');await btn('取消').click();assert.deepEqual((await state()).evaluation.claims.find(c=>c.id===seedClaim.id),seedClaim);
  });
  await t.test('Claim changes flag existing targets; target explicitly adopts updated definition',async()=>{
    await btn('编辑基本信息').click();await label('Claim 名称').fill('比例增加任务的理解与求解（修订）');await btn('保存修改').click();
    await go('targets?id='+seedTarget.id);await expect(page.locator('.requirement-card .callout')).toContainText('Claim 已更新');
    await page.getByRole('button',{name:'编辑要求 '+seedTarget.requirements[0].name,exact:true}).click();await expect(page.getByRole('dialog')).toContainText('从 v1 更新至 v2');await page.getByRole('checkbox',{name:/已核对：范围在 Claim 内/}).check();await btn('保存学习要求').click();await expect(page.locator('.requirement-card .callout')).toHaveCount(0);assert.equal((await state()).evaluation.targets.find(t=>t.id===seedTarget.id).requirements[0].claimVersion,2);
  });
  await t.test('a chapter supporting only one method cannot satisfy an all-method Claim',async()=>{
    await go('evaluation?id='+seedClaim.id);await btn('编辑条件').click();await label('方法要求').selectOption('all');await btn('保存修改').click();
    await go('textbooks?'+new URLSearchParams({tab:'import',source:seedBook.id,chapter:seedTarget.chapters[0],view:'links'}));await page.locator('.chapter-links').getByRole('button',{name:'编辑',exact:true}).click();
    const methods=(await state()).domain.methods.filter(m=>task.methods.includes(m.id));await label('本章采用 '+methods[1].name).uncheck();await btn('保存').click();
    await go('targets?id='+seedTarget.id);await expect(page.locator('.requirement-card .callout')).toContainText('不兼容');await page.getByRole('button',{name:'编辑要求 '+seedTarget.requirements[0].name,exact:true}).click();await expect(label('要求的方法覆盖')).toHaveValue('all');await page.getByRole('checkbox',{name:/已核对：范围在 Claim 内/}).check();await btn('保存学习要求').click();await expect(page.getByRole('alert')).toContainText('不兼容');await shot('04-method-conflict');await btn('取消').click();
    await go('textbooks?'+new URLSearchParams({tab:'import',source:seedBook.id,chapter:seedTarget.chapters[0],view:'links'}));await page.locator('.chapter-links').getByRole('button',{name:'编辑',exact:true}).click();await label('本章采用 '+methods[1].name).check();await btn('保存').click();
    await go('targets?id='+seedTarget.id);await page.getByRole('button',{name:'编辑要求 '+seedTarget.requirements[0].name,exact:true}).click();await page.getByRole('checkbox',{name:/已核对：范围在 Claim 内/}).check();await btn('保存学习要求').click();await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('.preparation')).toHaveCount(0);
  });
  await t.test('remove is scoped to target; route recovery, narrow layout and persistence',async()=>{
    await go('targets?id='+newTarget.id);await page.getByRole('button',{name:/移除要求 /}).click();await btn('取消').click();assert.equal((await state()).evaluation.targets.find(t=>t.id===newTarget.id).requirements.length,1);
    await page.getByRole('button',{name:/移除要求 /}).click();await btn('确认移除').click();assert.equal((await state()).evaluation.targets.find(t=>t.id===newTarget.id).requirements.length,0);assert.ok((await state()).evaluation.claims.some(c=>c.id===seedClaim.id));
    await go('evaluation?id=missing');await expect(page.getByRole('heading',{name:'当前浏览器中没有这个 Claim'})).toBeVisible();await go('targets?id=missing');await expect(page.getByRole('heading',{name:'当前浏览器中没有这个学习目标'})).toBeVisible();
    await page.setViewportSize({width:1024,height:850});await go('targets?id='+seedTarget.id);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await shot('05-target-1024');
    await go('evaluation?id='+seedClaim.id);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await shot('06-claim-1024');await page.setViewportSize({width:1440,height:1000});
    await go('targets');await shot('07-target-list');await go('evaluation');await shot('08-claim-list');
    assert.deepEqual(errors,[]);assert.deepEqual(api,[]);
    await writeFile(output+'review.json',JSON.stringify({screens,consoleErrors:errors,apiCalls:api,checks:['Claim independent of textbook','four aspects in one Claim','target reuse and scope','aspect reasons','explicit version adoption','method compatibility','remove and cancel','reload and narrow viewport']},null,2));
  });
});
