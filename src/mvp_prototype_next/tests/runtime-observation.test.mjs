import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from '../../mvp_prototype/node_modules/playwright/index.mjs';
import {expect} from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import {createPrototypeServer} from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/runtime-observation-review-20261024/',import.meta.url));
await mkdir(output,{recursive:true});
test('space observation follows shared runtime records and retains scope and provenance',async t=>{
  const server=createPrototypeServer({directory:output,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model calls expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`,browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=(p,name)=>p.getByRole('button',{name,exact:true}),dialog=p=>p.getByRole('dialog');
  const metric=(p,name)=>p.locator('.observation-metrics .metric-card').filter({has:p.getByText(name,{exact:true})}).locator('strong');
  async function journey(name,run,hash='objects',expectedApi=[]){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'}),p=await ctx.newPage(),errors=[],calls=[];
      p.setDefaultTimeout(6000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
      try{await p.goto(base+'#/'+hash);await run(p);assert.deepEqual(errors,[]);assert.deepEqual(calls.map(url=>new URL(url).pathname),expectedApi);}
      catch(e){await p.screenshot({path:output+'/failure-'+name.slice(0,30).replace(/\W/g,'-')+'.png',fullPage:true});throw e;}
      finally{await ctx.close();}
    });
  }
  await journey('activity usage and isolated scopes',async p=>{
    await expect(metric(p,'期间任务引用')).toHaveText('3');await expect(metric(p,'涉及 Task')).toHaveText('2');
    await expect(p.locator('.observation-records tbody tr')).toHaveCount(3);await expect(btn(p,'编辑')).toHaveCount(0);
    await btn(p,'查看依据 use:SPACE-ACT-001').click();await expect(dialog(p)).toContainText('KC 只经方法依赖汇总');await btn(p,'追溯活动步骤 →').click();
    await expect(p.getByRole('tab',{name:'采用定义',exact:true})).toHaveAttribute('aria-selected','true');await btn(p,'← 返回空间观测').click();await expect(dialog(p)).toContainText('SPACE-ACT-001');await btn(p,'关闭对话框').click();
    await p.getByLabel('观测范围',{exact:true}).selectOption('SPACE-002');await expect(metric(p,'期间任务引用')).toHaveText('0');
    await btn(p,'按对象查阅依据 →').click();await expect(p.locator('.observation-records')).toContainText('三角形');
    await btn(p,'查看依据 definition:geometry').click();await btn(dialog(p),'查看当前定义 →').click();await expect(btn(p,'← 返回空间观测')).toBeVisible();await btn(p,'← 返回空间观测').click();
    await expect(dialog(p)).toContainText('三角形');await btn(p,'关闭对话框').click();await btn(p.locator('#nav-objects'),'评估空间').click();
    await expect(p.getByLabel('观测范围',{exact:true})).toHaveValue('SPACE-002');await expect(metric(p,'期间 Evidence')).toHaveText('0');await expect(metric(p,'当前待确认要求')).toHaveText('4');
    await p.goto(base+'#/objects?tab=Evaluation&scope=NO-SUCH-SPACE');await expect(p.getByRole('alert')).toContainText('所选学习空间不存在');await expect(p.locator('.observation-metrics')).toHaveCount(0);
  });
  await journey('period changes versus current state',async p=>{
    await expect(metric(p,'期间 Evidence')).toHaveText('4');await expect(metric(p,'当前待确认要求')).toHaveText('6');
    await p.getByLabel('变化时间').selectOption('custom');await p.getByLabel('开始日期').fill('2026-10-23');await p.getByLabel('结束日期').fill('2026-10-23');
    await expect(metric(p,'期间 Evidence')).toHaveText('1');await expect(metric(p,'期间 Belief 更新')).toHaveText('1');await expect(metric(p,'当前待确认要求')).toHaveText('6');
    await p.getByLabel('记录类型').selectOption('Evidence');await expect(p.locator('.observation-records tbody tr')).toHaveCount(1);await btn(p,'查看依据 evidence:SPACE-EV-002').click();
    await expect(dialog(p)).toContainText('SPACE-EV-002');await btn(p,'追溯活动步骤 →').click();await expect(p.locator('.audit-step-detail h3')).toHaveText('解释 Evidence');await expect(p.locator('.page-header')).toContainText('SPACE-ACT-002');
    await btn(p,'← 返回空间观测').click();await expect(dialog(p)).toContainText('SPACE-EV-002');await btn(p,'关闭对话框').click();await expect(p.getByLabel('开始日期')).toHaveValue('2026-10-23');
    await p.getByLabel('搜索观测记录').fill('CLAIM-GEOMETRY');await expect(p.locator('.observation-records tbody tr')).toHaveCount(1);await p.getByLabel('搜索观测记录').fill('找不到的记录');await expect(p.locator('.observation-records tbody tr')).toHaveCount(0);await expect(metric(p,'期间 Evidence')).toHaveText('1');
    await p.getByLabel('开始日期').fill('2026-10-25');await expect(p.getByRole('alert')).toContainText('开始日期不能晚于结束日期');await expect(p.locator('.observation-metrics')).toHaveCount(0);
  },'objects?tab=Evaluation&scope=SPACE-001');
  await journey('evidence gap and requirement references',async p=>{
    await btn(p,'讲解后的理解尚未再验证').first().click();await expect(dialog(p)).toContainText('不是调用失败');await btn(p,'查看评价依据 →').click();
    await expect(p.getByRole('tab',{name:'评价结果',exact:true})).toHaveAttribute('aria-selected','true');await expect(p.locator('.round-results')).toContainText('需加强');await btn(p,'← 返回空间观测').click();await btn(p,'关闭对话框').click();
    await p.getByLabel('记录类型').selectOption('定义条件');await btn(p,'查看依据 conditions:SPACE-001:CLAIM-FRACTION').click();
    await expect(dialog(p)).toContainText('不自动裁剪 Claim');await btn(p,'查看当前目标要求 →').click();await expect(btn(p,'← 返回空间观测')).toBeVisible();await btn(p,'← 返回空间观测').click();await btn(p,'关闭对话框').click();
    await p.getByLabel('记录类型').selectOption('');await btn(p,'按对象查阅依据 →').click();await btn(p,'查看依据 state:SPACE-001:CLAIM-GEOMETRY').click();
    await expect(dialog(p)).toContainText('迁移');await expect(dialog(p)).toContainText('尚未形成判断');await expect(dialog(p)).not.toContainText('KC 掌握');await btn(p,'关闭对话框').click();
    await btn(p,'返回运行记录 →').click();await p.screenshot({path:output+'/evaluation-desktop.png',fullPage:true});
  },'objects?tab=Evaluation&scope=SPACE-001');
  await journey('review is distinct from execution and personal evaluation',async p=>{
    await expect(metric(p,'期间轮次快照')).toHaveText('4');await expect(metric(p,'期间实际行动')).toHaveText('2');await expect(metric(p,'人工标记疑点')).toHaveText('1');
    await p.getByLabel('记录类型').selectOption('交互状态快照');await btn(p,'查看依据 context:SPACE-ACT-001:F-R2').click();await expect(dialog(p)).toContainText('未记录活动是否仍在进行');await btn(p,'关闭对话框').click();
    await p.getByLabel('记录类型').selectOption('人工复核');await btn(p,'查看依据 review:SPACE-ACT-001').click();await expect(dialog(p)).toContainText('处理完成');await btn(p,'追溯活动步骤 →').click();
    await p.getByLabel('审查结论').selectOption('recorded');await p.getByLabel('结论与依据').fill('示例复核完成；保留原个人评价和配置待核对项。');await btn(p,'保存审查记录').click();await btn(p,'← 返回空间观测').click();
    await expect(dialog(p)).toContainText('已记录复核');await expect(dialog(p)).toContainText('观察候选的帮助误判');await btn(p,'关闭对话框').click();await expect(metric(p,'人工标记疑点')).toHaveText('0');
    await btn(p.locator('#nav-objects'),'评估空间').click();await expect(metric(p,'期间 Evidence')).toHaveText('4');await expect(metric(p,'当前需加强要求')).toHaveText('1');await expect(p.locator('.attention-panel')).toContainText('采用条件待核对');
  },'objects?tab=Interaction&scope=SPACE-001');
  await journey('rejected candidates retain exact retry trace',async p=>{
    await expect(p.locator('.attention-panel h3')).toContainText('拒绝与失败记录');await expect(metric(p,'示例候选生成')).toHaveText('5');await expect(metric(p,'示例校验拒绝')).toHaveText('1');await expect(metric(p,'示例结果提交')).toHaveText('4');await expect(metric(p,'示例模型调用')).toHaveText('5');
    await btn(p,'校验候选：拒绝').first().click();await expect(dialog(p)).toContainText('候选被拒绝');await expect(dialog(p)).toContainText('处理完成');await btn(p,'追溯活动步骤 →').click();
    await expect(p.locator('.audit-step-detail h3')).toHaveText('校验候选：拒绝');await expect(p.locator('.round-button').nth(1)).toHaveAttribute('aria-pressed','true');await btn(p,'← 返回空间观测').click();await btn(p,'关闭对话框').click();
    await p.screenshot({path:output+'/reasoning-desktop.png',fullPage:true});
  },'objects?tab=Reasoning');
  await journey('current edits appear without replacing adopted snapshots',async p=>{
    await btn(p,'查看依据 adopted:SPACE-001:CLAIM-GEOMETRY').click();await dialog(p).getByText('查看已记录原始内容',{exact:true}).click();const original=await dialog(p).locator('pre').innerText();
    await btn(p,'查看当前 Claim →').click();await btn(p,'编辑基本定义').click();await dialog(p).getByLabel('Claim 名称').fill('观测自查：修改当前定义');await btn(dialog(p),'保存').click();await btn(p,'← 返回空间观测').click();
    await dialog(p).getByText('查看已记录原始内容',{exact:true}).click();assert.equal(await dialog(p).locator('pre').innerText(),original);await expect(dialog(p)).toContainText('当前目录有变化');await btn(p,'关闭对话框').click();
    await btn(p,'模型变更').click();await expect(metric(p,'期间定义修改')).toHaveText('1');await expect(metric(p,'当前采用差异')).toHaveText('1');
    await btn(p,'查看依据 adoption:SPACE-001:CLAIM-GEOMETRY').click();await dialog(p).getByText('查看已记录原始内容',{exact:true}).click();await expect(dialog(p).locator('pre')).toContainText('观测自查：修改当前定义');await expect(dialog(p)).toContainText('未自动更新');await btn(p,'关闭对话框').click();
    await p.screenshot({path:output+'/definition-changes.png',fullPage:true});await btn(p.locator('#nav-objects'),'学习空间').click();await expect(metric(p,'采用内容有变化')).toHaveText('1');
    await p.getByLabel('记录类型').selectOption('课程采用记录');await expect(p.locator('.observation-records tbody tr')).toHaveCount(1);await btn(p,'查看依据 course-history:SPACE-001:0').click();await expect(dialog(p)).toContainText('学生本人');await btn(dialog(p),'查看学习空间 →').click();await btn(p,'← 返回空间观测').click();await expect(dialog(p)).toContainText('创建空间');
  },'objects?tab=Evaluation&scope=SPACE-001&result=catalog');
  await journey('legacy source real boundary and responsive layout',async p=>{
    await p.setViewportSize({width:1024,height:900});await expect(p.locator('.observation-metrics')).toBeVisible();
    assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);await p.screenshot({path:output+'/narrow-1024.png',fullPage:true});
    await p.goto(base+'#/objects?tab=Domain&id=missing');await expect(dialog(p)).toContainText('不会用其他学生');await btn(p,'关闭对话框').click();
    await p.getByText('数据口径与历史示例',{exact:true}).click();await btn(p,'查看旧版历史观测 →').click();await expect(p.locator('.space-browser')).toBeVisible();await expect(p.locator('.space-nav')).toHaveCount(0);
    await btn(p,'返回当前空间观测 →').click();await expect(p.locator('.runtime-observation')).toBeVisible();await expect(p.locator('.observation-nav')).toHaveCount(0);
    await p.getByLabel('数据来源',{exact:true}).selectOption('real');await expect(p.getByRole('heading',{name:'尚未接入真实模型数据'})).toBeVisible();await expect(p.locator('.observation-metrics')).toHaveCount(0);
  },'objects?tab=Evaluation');
  await journey('sidebar groups own navigation and preserve observation context',async p=>{
    const sidebar=p.locator('.sidebar'),observation=sidebar.getByRole('group',{name:'空间观测',exact:true});
    await expect(observation.getByRole('button')).toHaveCount(6);await expect(btn(sidebar,'空间观测')).toHaveAttribute('aria-expanded','true');
    await expect(btn(observation,'评估空间')).toHaveAttribute('aria-current','page');await expect(p.locator('.page-container nav')).toHaveCount(0);
    const original=p.url();await btn(sidebar,'空间观测').click();assert.equal(p.url(),original);await expect(observation).toBeHidden();
    await btn(sidebar,'空间观测').focus();await p.keyboard.press('Enter');await expect(observation).toBeVisible();
    await btn(observation,'交互空间').click();await expect(p.getByLabel('观测范围',{exact:true})).toHaveValue('SPACE-001');
    await expect(p.getByLabel('开始日期')).toHaveValue('2026-10-22');await expect(p.getByLabel('结束日期')).toHaveValue('2026-10-23');
    const switched=new URL(p.url().split('#')[1],'http://local');assert.equal(switched.searchParams.get('filter'),null);assert.equal(switched.searchParams.get('q'),null);assert.equal(switched.searchParams.get('review'),null);assert.equal(switched.searchParams.get('id'),null);
    await p.goBack();await expect(btn(observation,'评估空间')).toHaveAttribute('aria-current','page');await p.goForward();await p.reload();await expect(btn(observation,'交互空间')).toHaveAttribute('aria-current','page');
    await btn(sidebar,'模型管理').click();const models=sidebar.getByRole('group',{name:'模型管理',exact:true});await expect(models.getByRole('button')).toHaveText(['领域空间','评估空间']);
    await btn(models,'领域空间').click();await expect(p).toHaveURL(/#\/domain$/);await expect(btn(models,'领域空间')).toHaveAttribute('aria-current','page');
    await btn(models,'评估空间').click();await expect(p).toHaveURL(/#\/evaluation$/);await expect(btn(models,'评估空间')).toHaveAttribute('aria-current','page');
    await btn(sidebar,'课程管理').click();const courses=sidebar.getByRole('group',{name:'课程管理',exact:true});await expect(courses.getByRole('button')).toHaveText(['教材管理','学习目标','学习空间']);
    for(const [label,page] of [['教材管理','textbooks'],['学习目标','targets'],['学习空间','learning-spaces']]){await btn(courses,label).click();await expect(p).toHaveURL(new RegExp('#/'+page+'$'));await expect(btn(courses,label)).toHaveAttribute('aria-current','page');}
    await p.goto(base+'#/targets?id=TG-001');await expect(btn(sidebar,'课程管理')).toHaveAttribute('aria-expanded','true');await expect(btn(courses,'学习目标')).toHaveAttribute('aria-current','page');
    await p.goto(base+'#/objects?tab=Evaluation&scope=SPACE-001');await expect(p.locator('.sidebar [aria-current="page"]')).toHaveCount(1);
    await p.screenshot({path:output+'/sidebar-desktop.png',fullPage:true});await p.setViewportSize({width:1024,height:768});
    assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);await p.screenshot({path:output+'/sidebar-1024.png',fullPage:true});
    await btn(sidebar,'系统配置').click();await expect(p).toHaveURL(/#\/config$/);await expect(btn(sidebar,'系统配置')).toHaveAttribute('aria-current','page');
  },'objects?tab=Evaluation&scope=SPACE-001&range=custom&since=2026-10-22&until=2026-10-23&filter=Evidence&q=SPACE&review=attention',['/api/live/status']);
});
