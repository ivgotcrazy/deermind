import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from '../../mvp_prototype/node_modules/playwright/index.mjs';
import {expect} from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import {createPrototypeServer} from '../scripts/serve.mjs';
import {build} from '../admin/node_modules/esbuild/lib/main.js';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/runtime-overview-review-20261024/',import.meta.url));
await mkdir(output,{recursive:true});
test('one failed activity is not counted again for its round and step',async()=>{
  const bundled=await build({stdin:{contents:"export {overviewData} from './runtime-overview'; export {activityAudits} from './activity-review-mock';",resolveDir:fileURLToPath(new URL('../admin/src/workbench/',import.meta.url)),loader:'ts'},bundle:true,write:false,format:'esm',platform:'browser',define:{'process.env.NODE_ENV':'"production"'}});
  const {overviewData,activityAudits}=await import('data:text/javascript;base64,'+Buffer.from(bundled.outputFiles[0].text).toString('base64'));
  const audit=activityAudits['SPACE-ACT-001'];
  assert.equal(overviewData('','all','','').attention.filter(r=>r.group==='execution').length,0);
  audit.execution='failed';audit.rounds[1].execution='failed';audit.rounds[1].steps.find(s=>s.type==='belief.infer').status='failed';
  let data=overviewData('','all','','');let issues=data.attention.filter(r=>r.group==='execution');
  assert.equal(issues.length,1);assert.equal(issues[0].values.round,'F-R2');assert.equal(issues[0].values.span,'F-R2-belief');assert.equal(data.executions.find(s=>s.id==='failed').value,1);assert.equal(data.rejected,1);
  audit.execution='completed';audit.rounds[1].execution='completed';
  data=overviewData('','all','','');issues=data.attention.filter(r=>r.group==='execution');
  assert.equal(issues.length,1);assert.equal(issues[0].status,'处理完成');assert.equal(data.executions.find(s=>s.id==='failed').value,0);
  assert.equal(overviewData('SPACE-002','all','','').attention.filter(r=>r.group==='execution').length,0);
  assert.equal(overviewData('','custom','2026-10-23','2026-10-24').attention.filter(r=>r.group==='execution').length,0);
  delete activityAudits['SPACE-ACT-001'];
  data=overviewData('','all','','');assert.equal(data.unrecorded,1);assert.equal(data.executions.find(s=>s.id==='completed').value,2);
});
test('runtime overview connects current activity and space projections with distinct outcomes',async t=>{
  const server=createPrototypeServer({directory:output,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model calls expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`,browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=(p,name)=>p.getByRole('button',{name,exact:true}),dialog=p=>p.getByRole('dialog');
  const metric=(p,name)=>p.locator('.overview-metrics .metric-card').filter({has:p.getByText(name,{exact:true})}).locator('strong');
  const section=(p,name)=>p.locator('.overview-modules tbody tr').filter({has:p.getByText(name,{exact:true})});
  async function journey(name,run,hash='dashboard',allowApi=false){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'}),p=await ctx.newPage(),errors=[],calls=[];
      p.setDefaultTimeout(7000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
      try{await p.goto(base+'#/'+hash);await run(p);assert.deepEqual(errors,[]);if(!allowApi)assert.deepEqual(calls,[]);}
      catch(e){await p.screenshot({path:output+'/failure-'+name.slice(0,30).replace(/\W/g,'-')+'.png',fullPage:true});throw e;}
      finally{await ctx.close();}
    });
  }
  await journey('shared totals and exact drilldown',async p=>{
    await expect(metric(p,'学习活动')).toHaveText('3');await expect(metric(p,'处理轮次')).toHaveText('4');await expect(metric(p,'模型调用（示例）')).toHaveText('5');await expect(metric(p,'审查有疑点')).toHaveText('1');
    await expect(p.locator('.overview-metrics')).toContainText('1 名学生 · 1 个学习空间');await expect(p.locator('.execution-grid')).toContainText('处理失败0');
    await expect(p.locator('.overview-modules tbody tr')).toHaveCount(6);await expect(section(p,'Evaluation Space')).toContainText('已达标 1 / 需加强 1 / 待确认 18');
    await expect(p.locator('.workbench-context')).toContainText('刷新后恢复初始内容');await expect(btn(p,'导出工作记录')).toHaveCount(0);
    await metric(p,'学习活动').click();await expect(p.locator('.audit-list-table tbody tr')).toHaveCount(3);await expect(p.locator('.audit-list-table')).toContainText('SPACE-ACT-003');await btn(p,'← 返回运行总览').click();
    await metric(p,'模型调用（示例）').click();await expect(p.getByLabel('记录类型')).toHaveValue('模型调用');await expect(p.locator('.observation-records tbody tr')).toHaveCount(5);await btn(p,'← 返回运行总览').click();
    await p.screenshot({path:output+'/overview-desktop.png',fullPage:true});
  });
  await journey('date filtering preserves snapshot boundary and navigation',async p=>{
    await expect(metric(p,'学习活动')).toHaveText('1');await expect(metric(p,'处理轮次')).toHaveText('1');await expect(metric(p,'模型调用（示例）')).toHaveText('1');await expect(metric(p,'审查有疑点')).toHaveText('0');
    await expect(section(p,'Evaluation Space')).toContainText('已达标 1 / 需加强 1 / 待确认 6');
    await p.locator('.evaluation-counts').getByRole('button',{name:'Evidence 1',exact:true}).click();await expect(p.getByLabel('观测范围',{exact:true})).toHaveValue('SPACE-001');await expect(p.getByLabel('开始日期')).toHaveValue('2026-10-23');await expect(p.locator('.observation-records tbody tr')).toHaveCount(1);
    await btn(p,'查看依据 evidence:SPACE-EV-002').click();await btn(p,'追溯活动步骤 →').click();await expect(p.locator('.audit-step-detail h3')).toHaveText('解释 Evidence');await btn(p,'← 返回空间观测').click();await btn(p,'关闭对话框').click();await btn(p,'← 返回运行总览').click();
    await expect(p.getByLabel('运行范围')).toHaveValue('SPACE-001');await btn(p,'2026-10-23：1 项活动，查看当天活动').click();await expect(p.getByLabel('学习空间',{exact:true})).toHaveValue('SPACE-001');await expect(p.locator('.audit-list-table tbody tr')).toHaveCount(1);await btn(p,'← 返回运行总览').click();
    await p.getByLabel('开始日期').fill('2026-10-25');await expect(p.getByRole('alert')).toContainText('开始日期不能晚于结束日期');await expect(p.locator('.overview-metrics')).toHaveCount(0);
  },'dashboard?scope=SPACE-001&range=custom&since=2026-10-23&until=2026-10-23');
  await journey('candidate rejection does not become failed execution',async p=>{
    await p.getByRole('tab',{name:'执行问题 0',exact:true}).click();await expect(p.locator('.overview-attention')).toContainText('暂无已记录的执行问题');
    await btn(p,'另看候选拒绝记录 1 →').click();await expect(p.getByLabel('记录类型')).toHaveValue('语义校验');await expect(p.locator('.observation-records tbody tr')).toHaveCount(1);await btn(p,'查看依据 step:F-R2-reject').click();await expect(dialog(p)).toContainText('处理完成');await btn(p,'追溯活动步骤 →').click();await expect(p.locator('.audit-step-detail h3')).toHaveText('校验候选：拒绝');
    await btn(p,'← 返回空间观测').click();await btn(p,'关闭对话框').click();await btn(p,'← 返回运行总览').click();await expect(p.getByRole('tab',{name:'执行问题 0',exact:true})).toHaveAttribute('aria-selected','true');
    await p.getByRole('tab',{name:'评价依据 1',exact:true}).click();await btn(p,'追溯 gap:SPACE-ACT-003').click();await expect(dialog(p)).toContainText('不是调用失败');
  });
  await journey('review updates flow back without changing learning results',async p=>{
    await btn(p,'追溯 review:SPACE-ACT-001').click();await expect(p.getByRole('tab',{name:'审查记录',exact:true})).toHaveAttribute('aria-selected','true');
    await p.getByLabel('审查结论').selectOption('recorded');await p.getByLabel('结论与依据').fill('人工复核已记录，保留配置差异及原始评价。');await btn(p,'保存审查记录').click();await btn(p,'← 返回运行总览').click();
    await expect(metric(p,'审查有疑点')).toHaveText('0');await expect(p.getByRole('tab',{name:'内容与条件 6',exact:true})).toBeVisible();await expect(section(p,'Evaluation Space')).toContainText('已达标 1 / 需加强 1 / 待确认 18');await expect(p.locator('.overview-activities')).toContainText('已记录复核');
  });
  await journey('isolated empty scopes and invalid ids',async p=>{
    await p.getByLabel('运行范围').selectOption('SPACE-002');await expect(metric(p,'学习活动')).toHaveText('0');await expect(metric(p,'模型调用（示例）')).toHaveText('0');await expect(p.locator('.overview-activities tbody tr')).toHaveCount(0);await expect(section(p,'Evaluation Space')).toContainText('已达标 0 / 需加强 0 / 待确认 4');await expect(p.getByRole('tab',{name:'评价依据 0',exact:true})).toBeVisible();
    await btn(p,'观测 Evaluation Space').click();await expect(p.getByLabel('观测范围',{exact:true})).toHaveValue('SPACE-002');await btn(p,'← 返回运行总览').click();
    await p.goto(base+'#/dashboard?scope=NO-SUCH-SPACE');await expect(p.getByRole('alert')).toContainText('未扩大为全部学生');await expect(p.locator('.overview-metrics')).toHaveCount(0);
    await p.goto(base+'#/dashboard?range=invalid');await expect(p.getByRole('alert')).toContainText('时间范围不存在');
  });
  await journey('current condition records remain outside event window',async p=>{
    await expect(metric(p,'学习活动')).toHaveText('0');await expect(p.getByRole('tab',{name:'内容与条件 6',exact:true})).toBeVisible();await expect(p.getByRole('tab',{name:'评价依据 1',exact:true})).toBeVisible();
    await p.getByRole('tab',{name:'内容与条件 6',exact:true}).click();await btn(p,'追溯 conditions:SPACE-001:CLAIM-FRACTION').click();await expect(dialog(p)).toContainText('采用条件待核对');await expect(dialog(p)).toContainText('配置差异不等于学生能力不足');await btn(p,'关闭对话框').click();await btn(p,'← 返回运行总览').click();
    await expect(p.getByLabel('开始日期')).toHaveValue('2020-01-01');
  },'dashboard?range=custom&since=2020-01-01&until=2020-01-02');
  await journey('definition changes use current shared history and deduplicate adoption gaps',async p=>{
    await btn(p,'观测 Evaluation Space').click();await btn(p,'按对象查阅依据 →').click();await btn(p,'查看依据 adopted:SPACE-001:CLAIM-GEOMETRY').click();await btn(p,'查看当前 Claim →').click();
    await btn(p,'编辑基本定义').click();await dialog(p).getByLabel('Claim 名称').fill('总览自查：当前定义修改');await btn(dialog(p),'保存').click();await btn(p,'← 返回空间观测').click();await btn(p,'关闭对话框').click();await btn(p,'← 返回运行总览').click();
    await expect(section(p,'模型变更')).toContainText('期间定义修改 1');await expect(section(p,'模型变更')).toContainText('当前采用差异 1 项');
    await p.getByRole('tab',{name:'内容与条件 5',exact:true}).click();await expect(btn(p,'追溯 adoption:SPACE-001:CLAIM-GEOMETRY')).toHaveCount(1);
    await btn(p,'追溯 adoption:SPACE-001:CLAIM-GEOMETRY').click();await expect(dialog(p)).toContainText('未自动更新');
  },'dashboard?scope=SPACE-001');
  await journey('responsive view and bounded daily chart',async p=>{
    await p.setViewportSize({width:1024,height:900});assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);await p.screenshot({path:output+'/overview-1024.png',fullPage:true});
    await p.locator('.overview-modules').scrollIntoViewIfNeeded();await p.screenshot({path:output+'/modules-1024.png',fullPage:true});
    await p.goto(base+'#/dashboard?range=custom&since=2026-09-01&until=2026-10-24');await expect(p.locator('.day-bar')).toHaveCount(14);await expect(p.locator('.trend-panel')).toContainText('顶部统计仍覆盖整个期间');await btn(p,'轮次数').click();await expect(btn(p,'2026-10-22：2 轮，查看当天活动')).toBeVisible();
    await p.getByRole('link',{name:'统计口径',exact:true}).click();await expect(p.locator('#overview-methods')).toHaveAttribute('open','');
  });
  await journey('real view stays separate and error link uses status',async p=>{
    await p.route('**/api/live/admin/sessions',r=>r.fulfill({json:{items:[{id:'NEXT-TEST-ERROR',scope:{space:'math-6b',label:'六下数学'},model:'fixture',phase:'chat',pending:false,error:true,createdAt:'2026-10-24',updatedAt:'2026-10-24',title:'错误会话桩',turns:1}],unreadable:[]}}));
    await p.getByLabel('数据来源',{exact:true}).selectOption('real');await expect(p.locator('.runtime-overview')).toHaveCount(0);await expect(p.locator('.metric-grid')).toContainText('可读取真实会话');
    await p.locator('.metric-card').filter({has:p.getByText('有错误记录的会话',{exact:true})}).click();await expect(p.getByLabel('处理状态',{exact:true})).toHaveValue('error');await expect(p.locator('.trace-list tbody tr')).toHaveCount(1);await expect(p.locator('.trace-list')).not.toContainText('SPACE-ACT-001');
    await p.locator('.sidebar').getByRole('button',{name:'运行总览',exact:true}).click();await p.getByLabel('数据来源',{exact:true}).selectOption('demo');await expect(metric(p,'学习活动')).toHaveText('3');
  },'dashboard',true);
});
