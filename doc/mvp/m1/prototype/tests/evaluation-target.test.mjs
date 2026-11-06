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
  const state=()=>page.evaluate(()=>({evaluation:JSON.parse(localStorage.getItem('deermind-m1-evaluation-v3')||'{}'),domain:JSON.parse(localStorage.getItem('deermind-m1-domain-v1')||'{}'),imports:JSON.parse(localStorage.getItem('deermind-m1-import-v1')||'[]')}));
  const shot=async name=>{await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:output+name+'.png',animations:'disabled'});screens.push(name);};
  let seedTarget,seedClaim,seedBook,task,manualClaim,newTarget;
  await t.test('Claim creation is independent of textbook; incomplete definitions stay pending',async()=>{
    await go('domain');await btn('新建领域').click();await label('领域名称').fill('无教材领域');await label('覆盖范围').fill('人工定义的学习任务');await btn('创建并进入').click();
    const domainId=(await state()).domain.domains[0].id;
    await btn('新建任务模板').click();await label('任务名称').fill('独立领域任务');await label('任务目标').fill('完成指定工作');await label('学习者承担的工作').fill('自行完成并说明');await btn('创建任务模板').click();
    const taskId=(await state()).domain.tasks[0].id;
    await go('evaluation');await btn('新建 Claim').click();await expect(label('帮助与工具条件')).toHaveCount(0);await label('所属领域').selectOption(domainId);await label('关联 Task').selectOption(taskId);await label('Claim 名称').fill('不依附教材的 Claim');await btn('创建 Claim').click();
    await expect(page.getByRole('heading',{name:'不依附教材的 Claim',exact:true})).toBeVisible();
    await expect(page.getByText(/项定义待补充或核对/)).toBeVisible();
    const data=await state();manualClaim=data.evaluation.claims[0];assert.equal(data.imports.length,0);assert.equal(manualClaim.aspects.length,4);assert.equal(manualClaim.taskId,taskId);assert.equal('bookId' in manualClaim,false);assert.equal('support' in manualClaim,false);
    await expect(page.getByText('帮助与工具条件',{exact:true})).toHaveCount(0);
    await btn('编辑基本信息').click();await label('Claim 名称').fill('取消的修改');await btn('取消').click();await page.reload();await expect(page.getByRole('heading',{name:'不依附教材的 Claim',exact:true})).toBeVisible();
  });
  await t.test('opt-in example connects Domain, one multidimensional Claim, textbook chapter and target',async()=>{
    await go('evaluation');await btn('打开四分之一样例').click();await expect(page.getByRole('heading',{name:'比例增加任务的理解与求解',exact:true})).toBeVisible();
    const data=await state();seedTarget=data.evaluation.targets.find(t=>t.id==='TARGET-M1-QUARTER-SEPARATE');seedClaim=data.evaluation.claims.find(c=>c.id===seedTarget.requirements[0].claimId);seedBook=data.imports.find(d=>d.book.id===seedTarget.bookId);task=data.domain.tasks.find(t=>t.id===seedClaim.taskId);
    assert.equal(data.evaluation.claims.length,3);assert.equal(seedClaim.aspects.length,4);assert.equal(seedClaim.taskVersion,task.version);assert.equal(seedTarget.requirements[0].standards.length,4);assert.ok(seedTarget.requirements[0].standards.find(s=>s.aspectId==='transfer').text.includes('表格'));assert.ok(seedTarget.requirements[0].standards.find(s=>s.aspectId==='retention').text.includes('7×24'));
    await shot('01-claim-definition');
    await go('targets?id='+seedTarget.id);await expect(page.getByRole('heading',{name:seedTarget.name,exact:true})).toBeVisible();await expect(page.locator('.preparation')).toHaveCount(0);await expect(page.getByText('帮助条件',{exact:true})).toHaveCount(0);await shot('02-target-requirements');
    const before=await state();await go('evaluation');await btn('打开四分之一样例').click();const after=await state();assert.deepEqual(after.domain,before.domain);assert.deepEqual(after.imports,before.imports);assert.equal(after.evaluation.targets.length,1);
  });
  await t.test('choosing a method switches both panels together and survives reload and browser navigation',async()=>{
    await go('evaluation?id='+seedClaim.id);
    const tabs=page.getByRole('tablist',{name:'当前方法'}).getByRole('tab');
    await expect(tabs).toHaveCount(2);
    const detail=page.getByRole('region',{name:'当前方法详情'});
    const execution=detail.getByRole('region',{name:'本方法执行判据'});
    const dimensions=detail.getByRole('region',{name:'四方面评价规则'});
    await expect(tabs.nth(0)).toHaveAttribute('aria-selected','true');
    await expect(execution).toContainText('把子方法的增加量用于求新量');
    await expect(dimensions.locator('[data-aspect="explanation"]')).toContainText('加回原量');
    await tabs.nth(1).click();
    await expect(execution).toContainText('按新量倍数计算');
    await expect(execution).not.toContainText('把子方法的增加量用于求新量');
    await expect(dimensions.locator('[data-aspect="explanation"]')).toContainText('1＋r');
    await expect(detail.getByRole('combobox')).toHaveCount(0);
    await page.reload();await expect(tabs.nth(1)).toHaveAttribute('aria-selected','true');
    await page.goBack();await expect(tabs.nth(0)).toHaveAttribute('aria-selected','true');
    await expect(dimensions.locator('[data-aspect="explanation"]')).toContainText('加回原量');
    await page.goForward();await expect(tabs.nth(1)).toHaveAttribute('aria-selected','true');
    await go('evaluation?id='+seedClaim.id+'&method=UNKNOWN');
    await expect(detail).toContainText('链接中的方法不属于当前 Task');
    await expect(detail.getByRole('region',{name:'四方面评价规则'})).toHaveCount(0);
    await tabs.nth(1).click();await expect(dimensions).toBeVisible();
    await tabs.nth(1).press('ArrowLeft');
    await expect(tabs.nth(0)).toBeFocused();
    await expect(execution).toContainText('把子方法的增加量用于求新量');
    await tabs.nth(0).press('End');await expect(tabs.nth(1)).toBeFocused();
    await expect(detail.getByRole('tabpanel',{name:'按原量的 1+r 倍计算',exact:true})).toContainText('四方面评价规则');
    await shot('01b-single-method-workspace');
  });
  await t.test('a second target reuses the Claim; selection and standards do not mutate its definition',async()=>{
    await go('targets');await btn('新建学习目标').click();await label('目标名称').fill('本周四分之一学习要求');await label('教材').selectOption(seedTarget.bookId);await label(seedTarget.chapters[0]).check();await btn('创建学习目标').click();
    newTarget=(await state()).evaluation.targets.find(t=>t.name==='本周四分之一学习要求');
    await btn('添加学习要求').click();await expect(label('选用 Claim').locator('option[value="'+manualClaim.id+'"]')).toHaveCount(0);await label('选用 Claim').selectOption(seedClaim.id);
    await label('学习要求名称').fill('自己求解并说明四分之一的参照量');await label('具体任务范围').fill(seedTarget.requirements[0].scope);
    for(const a of seedClaim.aspects)await label(a.name+'达标标准').fill(seedTarget.requirements[0].standards.find(s=>s.aspectId===a.id).text);
    await expect(page.getByRole('dialog')).not.toContainText('帮助与工具条件沿用 Claim');
    await btn('保存学习要求').click();await expect(page.getByRole('alert')).toContainText('请核对范围');
    await page.getByRole('checkbox',{name:/已核对：范围在 Task 内/}).check();await btn('保存学习要求').click();await expect(page.getByRole('dialog')).toHaveCount(0);
    const data=await state();assert.deepEqual(data.evaluation.claims.find(c=>c.id===seedClaim.id),seedClaim);assert.equal(data.evaluation.targets.find(t=>t.id===newTarget.id).requirements.length,1);
    await page.reload();await expect(page.getByRole('heading',{name:'自己求解并说明四分之一的参照量',exact:true})).toBeVisible();await shot('03-reused-claim-target');
    await btn('添加学习要求').click();await label('选用 Claim').selectOption(seedClaim.id);await label('学习要求名称').fill('另一个任务子范围');await label('具体任务范围').fill('增加比例 r=1/2；原量为正，离散数量满足整量条件。');
    for(const a of seedClaim.aspects)await label(a.name+'达标标准').fill(seedTarget.requirements[0].standards.find(s=>s.aspectId===a.id).text.replaceAll('四分之一','二分之一'));
    await page.getByRole('checkbox',{name:/已核对：范围在 Task 内/}).check();await btn('保存学习要求').click();assert.equal((await state()).evaluation.targets.find(t=>t.id===newTarget.id).requirements.length,2);assert.deepEqual((await state()).evaluation.claims.find(c=>c.id===seedClaim.id),seedClaim);
    await page.getByRole('button',{name:'移除要求 另一个任务子范围',exact:true}).click();await btn('确认移除').click();
  });
  await t.test('aspect settings share the basic-info draft, validation and one save',async()=>{
    await go('evaluation?id='+manualClaim.id);
    await expect(page.getByText('共同评价规则',{exact:true})).toHaveCount(0);
    await expect(page.locator('summary').filter({hasText:'管理评价方面'})).toHaveCount(0);
    await btn('编辑基本信息').click();
    await label('Claim 名称').fill('取消的名称');
    await label('启用迁移').uncheck();await btn('保存修改').click();
    await expect(page.getByRole('alert')).toContainText('裁剪或扩展依据');
    await label('迁移的裁剪或扩展依据').fill('本目标聚焦即时求解。');
    await btn('增加评价方面').click();await label('自定义方面名称').fill('结果合理性检查');
    await btn('保存修改').click();await expect(page.getByRole('alert')).toContainText('结果合理性检查');
    await btn('取消').click();await page.reload();
    assert.deepEqual((await state()).evaluation.claims.find(c=>c.id===manualClaim.id),manualClaim);
    await btn('编辑基本信息').click();
    for(const a of manualClaim.aspects)await label('启用'+a.name).uncheck();
    await btn('保存修改').click();await expect(page.getByRole('alert')).toContainText('至少保留一个');
    await btn('取消').click();

    await btn('编辑基本信息').click();
    await label('启用迁移').uncheck();await label('迁移的裁剪或扩展依据').fill('本轮只检查当前情境，另行组织迁移验证。');
    await btn('增加评价方面').click();await label('自定义方面名称').fill('独立完成');
    await btn('保存修改').click();await expect(page.getByRole('alert')).toContainText('名称不能重复');
    await label('自定义方面名称').fill('结果合理性检查');
    await label('结果合理性检查的裁剪或扩展依据').fill('需要依据数量变化方向检查结果。');
    await shot('aspect-basic-editor');await btn('保存修改').click();await page.reload();
    const saved=(await state()).evaluation.claims.find(c=>c.id===manualClaim.id);
    assert.equal(saved.version,manualClaim.version+1);
    await btn('编辑基本信息').click();
    await expect(label('启用迁移')).not.toBeChecked();await expect(label('启用结果合理性检查')).toBeChecked();
    await expect(label('迁移的裁剪或扩展依据')).toHaveValue('本轮只检查当前情境，另行组织迁移验证。');
    await btn('取消').click();
    await go('evaluation?id='+seedClaim.id);
  });
  await t.test('Claim changes flag existing targets; target explicitly adopts updated definition',async()=>{
    await btn('编辑基本信息').click();await label('Claim 名称').fill('比例增加任务的理解与求解（修订）');await btn('保存修改').click();
    await go('targets?id='+seedTarget.id);await expect(page.locator('.requirement-card .callout')).toContainText('Claim 已更新');
    await page.getByRole('button',{name:'编辑要求 '+seedTarget.requirements[0].name,exact:true}).click();await expect(page.getByRole('dialog')).toContainText('从 v1 更新至 v2');await page.getByRole('checkbox',{name:/已核对：范围在 Task 内/}).check();await btn('保存学习要求').click();await expect(page.locator('.requirement-card .callout')).toHaveCount(0);assert.equal((await state()).evaluation.targets.find(t=>t.id===seedTarget.id).requirements[0].claimVersion,2);
  });
  await t.test('method coverage belongs to the target; incompatible chapters cannot satisfy both selected methods',async()=>{
    await go('targets?id='+seedTarget.id);
    await btn('编辑要求 '+seedTarget.requirements[0].name).click();
    await label('要求的方法覆盖').selectOption('all');
    await page.getByRole('checkbox',{name:/已核对：范围在 Task 内/}).check();
    await btn('保存学习要求').click();
    await expect(page.locator('.method-standards tbody')).toHaveCount(2);
    for(const group of await page.locator('.method-standards tbody').all())await expect(group).toContainText('2 道不同的新题');
    await shot('04-both-methods-required');
    await go('textbooks?'+new URLSearchParams({tab:'import',source:seedBook.id,chapter:seedTarget.chapters[0],view:'links'}));await page.locator('.chapter-links').getByRole('button',{name:'编辑',exact:true}).click();
    const methods=(await state()).domain.methods.filter(m=>task.methods.includes(m.id));await label('本章采用 '+methods[1].name).uncheck();await btn('保存').click();
    await go('targets?id='+seedTarget.id);await expect(page.locator('.requirement-card .callout')).toContainText('不兼容');await page.getByRole('button',{name:'编辑要求 '+seedTarget.requirements[0].name,exact:true}).click();await expect(label('要求的方法覆盖')).toHaveValue('all');await page.getByRole('checkbox',{name:/已核对：范围在 Task 内/}).check();await btn('保存学习要求').click();await expect(page.getByRole('alert')).toContainText('不兼容');await shot('04-method-conflict');await btn('取消').click();
    await go('textbooks?'+new URLSearchParams({tab:'import',source:seedBook.id,chapter:seedTarget.chapters[0],view:'links'}));await page.locator('.chapter-links').getByRole('button',{name:'编辑',exact:true}).click();await label('本章采用 '+methods[1].name).check();await btn('保存').click();
    await go('targets?id='+seedTarget.id);await page.getByRole('button',{name:'编辑要求 '+seedTarget.requirements[0].name,exact:true}).click();await page.getByRole('checkbox',{name:/已核对：范围在 Task 内/}).check();await btn('保存学习要求').click();await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('.preparation')).toHaveCount(0);
  });
  await t.test('remove is scoped to target; route recovery, narrow layout and persistence',async()=>{
    await go('targets?id='+newTarget.id);await page.getByRole('button',{name:/移除要求 /}).click();await btn('取消').click();assert.equal((await state()).evaluation.targets.find(t=>t.id===newTarget.id).requirements.length,1);
    await page.getByRole('button',{name:/移除要求 /}).click();await btn('确认移除').click();assert.equal((await state()).evaluation.targets.find(t=>t.id===newTarget.id).requirements.length,0);assert.ok((await state()).evaluation.claims.some(c=>c.id===seedClaim.id));
    await go('evaluation?id=missing');await expect(page.getByRole('heading',{name:'当前浏览器中没有这个 Claim'})).toBeVisible();await go('targets?id=missing');await expect(page.getByRole('heading',{name:'当前浏览器中没有这个学习目标'})).toBeVisible();
    await page.setViewportSize({width:1024,height:850});await go('targets?id='+seedTarget.id);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await shot('05-target-1024');
    await go('evaluation?id='+seedClaim.id);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await shot('06-claim-1024');await page.setViewportSize({width:1440,height:1000});
    await go('targets');await shot('07-target-list');await go('evaluation');await shot('08-claim-list');
    assert.deepEqual(errors,[]);assert.deepEqual(api,[]);

  });
  await t.test('create a criterion once, reuse it in method cells, cancel changes and update all references',async()=>{
    await go('evaluation?id='+seedClaim.id);
    await expect(page.getByText('评价范围',{exact:true})).toHaveCount(0);
    await expect(label('方法要求')).toHaveCount(0);
    const originalRules=(await state()).evaluation.claims.find(c=>c.id===seedClaim.id).rules;
    const shared='走查用可复用判据';
    const domain=(await state()).domain;
    const methods=task.methods.map(id=>domain.methods.find(m=>m.id===id).name);
    const cell=name=>btn(name+' · 关联执行判据');
    const shown=page.getByRole('region',{name:'本方法执行判据'});
    const choose=name=>page.getByRole('tab',{name,exact:true}).click();
    const library=page.locator('.criterion-library');
    async function openLibrary(){if(!await library.evaluate(el=>el.open))await library.locator('summary').first().click();}
    await openLibrary();
    await btn('新建判据').click();
    await label('判据名称').fill(shared);
    await label('必要输入').fill('实际算式或作答过程');
    await label('判定依据').fill('Task 中的数量关系');
    await label('满足的表现').fill('结果使用题目给定的单位');
    await label('不满足的表现').fill('把长度单位写成面积单位');
    await label('信息不足的情况').fill('作答中没有单位信息');
    await btn('保存判据').click();
    for(const name of methods){
      await choose(name);await cell(name).click();await label('选用 '+shared).check();await btn('保存关联').click();
      await expect(shown).toContainText(shared);
    }
    await expect(btn('删除判据 '+shared)).toBeDisabled();
    await btn('编辑判据 '+shared).click();await label('判据名称').fill(shared+'（修订）');await btn('保存判据').click();
    for(const name of methods){await choose(name);await expect(shown).toContainText(shared+'（修订）');}
    await choose(methods[0]);
    await cell(methods[0]).click();await label('选用 '+shared+'（修订）').uncheck();await btn('取消').click();
    await page.reload();await expect(shown).toContainText(shared+'（修订）');
    await cell(methods[0]).click();await page.getByRole('dialog').getByRole('button',{name:'新建判据',exact:true}).click();
    await label('判据名称').fill('从关联中创建');await label('满足的表现').fill('指出增加量与原量的关系');await btn('保存判据').click();
    await expect(label('选用 从关联中创建')).toBeChecked();await btn('取消').click();
    await expect(shown).not.toContainText('从关联中创建');await openLibrary();
    await btn('删除判据 从关联中创建').click();await btn('确认删除').click();
    await shot('09-method-execution');
    const before=(await state()).evaluation.claims.find(c=>c.id===seedClaim.id);
    assert.deepEqual(before.rules,originalRules);
    const aspectPanel=page.getByRole('region',{name:'四方面评价规则'});
    await choose(methods[1]);
    await expect(aspectPanel.locator('[data-aspect="explanation"]')).toContainText('1＋r');
    await btn('编辑理解与解释规则').click();
    await label('判断要求').fill('解释原量整体与增加分率，并说明倍数为什么是 1＋r。');
    await label('需要的证据').fill('学生对 1 和 r 的自主解释、实际帮助记录。');
    await btn('保存评价规则').click();
    const after=(await state()).evaluation.claims.find(c=>c.id===seedClaim.id);
    assert.deepEqual(after.executions,before.executions);
    assert.deepEqual(after.criteria,before.criteria);
    assert.deepEqual(after.rules.filter(r=>r.methodId===task.methods[0]),before.rules.filter(r=>r.methodId===task.methods[0]));
    assert.equal(after.rules.filter(r=>r.aspectId==='explanation'&&r.methodId===task.methods[1]).length,1);
    assert.equal(after.rules.some(r=>'criteria' in r),false);
    await shot('09b-aspect-rules');
    await page.reload();await expect(page.getByRole('tab',{name:methods[1],exact:true})).toHaveAttribute('aria-selected','true');
    await expect(aspectPanel.locator('[data-aspect="explanation"]')).toContainText('自主解释');
    await btn('编辑迁移规则').click();await label('需要的证据').fill('取消修改');await btn('取消').click();
    await expect(aspectPanel.locator('[data-aspect="transfer"]')).not.toContainText('取消修改');
    await expect(shown).toContainText('按新量倍数计算');
  });
  await t.test('expand the actual Domain call and edit child only at its source',async()=>{
    await go('targets?id='+seedTarget.id);
    await btn('编辑要求 '+seedTarget.requirements[0].name).click();
    await page.getByRole('checkbox',{name:/已核对：范围在 Task 内/}).check();
    await btn('保存学习要求').click();await expect(page.locator('.preparation')).toHaveCount(0);
    await go('evaluation?id='+seedClaim.id);
    await btn('展开子方法（1）').click();
    const child=page.locator('.child-source');
    await expect(child).toContainText('使用分数乘法求对应数量');
    await expect(child).toContainText('计算对应部分');await expect(child).toContainText('返回');
    const link=child.getByRole('link',{name:/求一个量的几分之几 · v/});
    const first=(await state()).evaluation.claims.find(c=>c.id===seedClaim.id);
    assert.ok(first.criteria.every(c=>c.name!=='计算对应部分'));
    await shot('10-domain-call-expanded');await link.click();
    await expect(page.getByRole('tab',{name:'使用分数乘法求对应数量',exact:true})).toHaveAttribute('aria-selected','true');
    await btn('编辑本层判据 计算对应部分').click();await label('判据名称').fill('核对部分量与单位');await btn('保存判据').click();
    await go('evaluation?id='+seedClaim.id);await btn('展开子方法（1）').click();
    await expect(page.locator('.child-source')).toContainText('核对部分量与单位');
    const parent=(await state()).evaluation.claims.find(c=>c.id===seedClaim.id);
    assert.deepEqual(parent,first);
    await go('targets?id='+seedTarget.id);await expect(page.locator('.requirement-card .callout')).toContainText('判据来源或方法版本已变更');
  });
  await t.test('unbinding a local criterion does not block a goal restricted to the other prepared method',async()=>{
    const all=(await state()).domain.methods;
    const first=all.find(m=>m.id===task.methods[0]).name;
    await go('evaluation?id='+seedClaim.id);
    await btn(first+' · 关联执行判据').click();
    const active=page.getByRole('dialog').locator('input[type=checkbox]:checked');
    while(await active.count())await active.first().uncheck();
    await btn('保存关联').click();
    await expect(page.getByRole('region',{name:'本方法执行判据'})).toContainText('待关联');
    await go('targets?id='+seedTarget.id);
    await btn('编辑要求 '+seedTarget.requirements[0].name).click();
    await page.getByRole('checkbox',{name:/已核对：范围在 Task 内/}).check();
    await btn('保存学习要求').click();
    await expect(page.getByRole('alert')).toContainText('尚未关联本层执行判据');
    await label(first).uncheck();await btn('保存学习要求').click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.locator('.preparation')).toHaveCount(0);
    // An explanation-only requirement can use explicit conceptual evidence on its own.
    await btn('编辑要求 '+seedTarget.requirements[0].name).click();
    await label(first).check();
    for(const name of ['独立完成','迁移','延迟保持'])await label(name).uncheck();
    await label('未纳入方面的依据').fill('此要求只核对学生能否解释方法的原理。');
    await page.getByRole('checkbox',{name:/已核对：范围在 Task 内/}).check();
    await btn('保存学习要求').click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.locator('.method-standards tbody')).toHaveCount(2);
    await expect(page.locator('.method-standards tbody tr')).toHaveCount(2);
  });
  await t.test('existing browser drafts keep identifiers, legacy text and only previous method associations',async()=>{
    const legacy={...seedClaim,scope:'旧稿局部范围',methods:[task.methods[0]],methodMode:'all',aspects:seedClaim.aspects.map(a=>({...a,criterion:'原有表现 '+a.name,insufficient:'原有缺口',counter:'原有反证'}))};
    delete legacy.criteria;delete legacy.rules;delete legacy.executions;
    const before={claims:[legacy],targets:[seedTarget]};
    const snapshot=await state();
    const isolated=await browser.newContext();
    try {
      await isolated.addInitScript(({snapshot,before})=>{
        if(localStorage.getItem('deermind-m1-evaluation-v1'))return;
        localStorage.setItem('deermind-m1-domain-v1',JSON.stringify(snapshot.domain));
        localStorage.setItem('deermind-m1-import-v1',JSON.stringify(snapshot.imports));
        localStorage.setItem('deermind-m1-evaluation-v1',JSON.stringify(before));
      },{snapshot,before});
      const old=await isolated.newPage();
      await old.goto(base+'/admin/#/evaluation?id='+seedClaim.id);
      await expect(old.getByRole('heading',{name:seedClaim.name})).toBeVisible();
      await old.getByText('旧版配置参考',{exact:true}).click();await expect(old.getByText(/原有表现 独立完成/).first()).toBeVisible();
      const read=async()=>old.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-evaluation-v3')));
      const migrated=await read();
      assert.equal(migrated.claims[0].version,legacy.version+2);
      assert.equal(migrated.claims[0].previous.criteria.length,4);assert.equal(migrated.claims[0].executions.length,0);
      assert.ok(migrated.claims[0].rules.every(r=>r.methodId===task.methods[0]));
      assert.equal('methods' in migrated.claims[0],false);
      assert.deepEqual(migrated.targets[0],seedTarget);
      await old.reload();assert.deepEqual(await read(),migrated);
      assert.deepEqual(await old.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-evaluation-v1'))),before);
      await old.goto(base+'/admin/#/targets?id='+seedTarget.id);await expect(old.locator('.requirement-card .callout')).toContainText('Claim 已更新');
    } finally {await isolated.close();}
  });
  await t.test('previous mixed drafts retain their sources and edited criteria are not reassigned by guesswork',async()=>{
    const snapshot=await state();
    const legacy=(id,name,version)=>({
      ...structuredClone(seedClaim),id,name,version,
      history:[{version,change:version===1?'载入比例增加任务的方法与判据':'用户自定义修改',at:'mock'}],
      criteria:[{...seedClaim.criteria[0],id:'F1'},{...seedClaim.criteria[0],id:'F2',met:'解释原量整体和增加分率'}],
      rules:[
        {methodId:task.methods[0],aspectId:'independent',criteria:['F1'],condition:'实际帮助记录'},
        {methodId:task.methods[0],aspectId:'explanation',criteria:['F2'],condition:'口述的原量关系'},
      ],
    });
    const sample=legacy('IMPORTED-SAMPLE','原样例',1),custom=legacy('IMPORTED-CUSTOM','自定义旧稿',4);
    delete sample.executions;delete custom.executions;
    const before={claims:[sample,custom],targets:[]};
    const isolated=await browser.newContext();
    try {
      await isolated.addInitScript(({snapshot,before})=>{
        if(localStorage.getItem('deermind-m1-evaluation-v2'))return;
        localStorage.setItem('deermind-m1-domain-v1',JSON.stringify(snapshot.domain));
        localStorage.setItem('deermind-m1-evaluation-v2',JSON.stringify(before));
      },{snapshot,before});
      const p=await isolated.newPage();
      await p.goto(base+'/admin/#/evaluation?id='+sample.id);
      await expect(p.getByRole('heading',{name:sample.name})).toBeVisible();
      const data=await p.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-evaluation-v3')));
      const imported=data.claims.find(c=>c.id===sample.id);
      assert.deepEqual(imported.executions[0].criteria,['F1']);
      assert.equal(imported.rules.find(r=>r.aspectId==='explanation').judgment,'解释原量整体和增加分率');
      const edited=data.claims.find(c=>c.id===custom.id);
      assert.equal(edited.executions.length,0);assert.deepEqual(edited.previous.criteria,custom.criteria);
      await p.goto(base+'/admin/#/evaluation?id='+custom.id);
      await p.getByText('旧版配置参考',{exact:true}).click();await expect(p.getByText('原来的引用',{exact:true})).toBeVisible();
      assert.deepEqual(await p.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-evaluation-v2'))),before);
      // Opening an already-saved v3 draft retires only the former Claim policy and stock wording.
      const oldDraft=structuredClone(data);
      oldDraft.claims[0].support='旧版通用条件';
      oldDraft.claims[0].rules[0].condition='记录允许的工具、实际采用的方法及当题帮助，核对关键步骤由学生承担。';
      oldDraft.claims[0].rules[0].judgment='在允许的工具与帮助边界内，学生自行选择方法、完成关键步骤，并达到方法的执行要求。';
      await p.evaluate(d=>localStorage.setItem('deermind-m1-evaluation-v3',JSON.stringify(d)),oldDraft);
      await p.reload();
      await expect(p.getByRole('heading',{name:custom.name})).toBeVisible();
      const cleaned=await p.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-evaluation-v3')));
      const expected=structuredClone(data);
      expected.claims[0].rules[0].condition='记录本次作答、实际获得的提示，以及关键步骤由谁完成。';
      assert.deepEqual(cleaned,expected);
    }finally{await isolated.close();}
  });
  await t.test('multiple recursion levels, repeated calls, missing sources and cycles retain their own paths',async()=>{
    const data=await state();
    const first=data.domain.methods.find(m=>m.id===task.methods[0]);
    const call=first.steps.find(s=>s.divided);
    const child=data.domain.methods.find(m=>m.id===call.solutionId);
    const childTask=data.domain.tasks.find(t=>t.id===call.taskId);
    const leaf={...structuredClone(child),id:'ST-TEST-LEAF',name:'走查第三层'};
    const leafTask={...structuredClone(childTask),id:'TT-TEST-LEAF',name:'第三层任务',methods:[leaf.id]};
    const substep={...structuredClone(call),title:'第三层调用',taskId:leafTask.id,solutionId:leaf.id};
    child.steps.push(substep);
    first.steps.push({...structuredClone(call),title:'再次调用，用于另一个输入'});
    data.domain.methods.push(leaf);data.domain.tasks.push(leafTask);
    leaf.steps.push({...structuredClone(call),title:'循环回子方法'});
    const isolated=await browser.newContext();
    try{
      await isolated.addInitScript(data=>{
        if(localStorage.getItem('deermind-m1-evaluation-v3'))return;
        localStorage.setItem('deermind-m1-domain-v1',JSON.stringify(data.domain));
        localStorage.setItem('deermind-m1-evaluation-v3',JSON.stringify(data.evaluation));
      },data);
      const p=await isolated.newPage();await p.goto(base+'/admin/#/evaluation?id='+seedClaim.id);
      await p.getByRole('button',{name:'展开子方法（2）'}).click();
      const branches=p.locator('.method-children > .child-source');
      await expect(branches).toHaveCount(2);
      await expect(branches.nth(1)).toContainText('再次调用，用于另一个输入');
      await branches.first().locator('summary').first().click();
      const nested=branches.first().locator(':scope > details > .child-source');
      await expect(nested).toContainText('子任务尚无 Claim');
      await nested.locator(':scope > details > summary').click();
      await expect(nested.locator(':scope > details > .child-source')).toContainText('分解路径重复');
    } finally {await isolated.close();}
  });
  assert.deepEqual(errors,[]);assert.deepEqual(api,[]);
  await writeFile(output+'review.json',JSON.stringify({screens,consoleErrors:errors,apiCalls:api},null,2));
});
