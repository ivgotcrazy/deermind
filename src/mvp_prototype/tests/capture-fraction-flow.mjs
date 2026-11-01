import assert from 'node:assert/strict';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { chromium, expect } from '@playwright/test';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../doc/mvp/phase-4-product-and-domain-foundation/assets/product-interaction/fraction-flow/',import.meta.url));
await mkdir(output,{recursive:true});
const errors=[],captures=[],checks=[];let modelCalls=0,completed=false;
const server=createPrototypeServer({directory:output,config:{key:'fixture',model:'fixed'},provider:async()=>{modelCalls++;throw Error('No model calls in product walkthrough');}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true,channel:'msedge'});
const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'});
const a=await context.newPage(),s=await context.newPage();
for(const p of [a,s]){p.setDefaultTimeout(12000);p.on('pageerror',e=>errors.push(e.message));}
const btn=(p,name)=>p.getByRole('button',{name,exact:true}),tab=(p,name)=>p.getByRole('tab',{name,exact:true});
const state=()=>a.evaluate(()=>JSON.parse(localStorage.getItem('deermind-next-learning-flow-v1')));
async function shot(p,id,title,locator){await p.evaluate(()=>document.fonts.ready);const bytes=await (locator||p).screenshot({path:output+'/'+id+'.png',animations:'disabled'});captures.push({id,title,file:id+'.png',route:new URL(p.url()).pathname+new URL(p.url()).hash,sha256:createHash('sha256').update(bytes).digest('hex'),viewport:p.viewportSize()});console.log(id+' '+title);}
async function sample(){const d=s.locator('.question-card').filter({has:s.locator('.question-title')});if(!await d.locator('details').getAttribute('open').then(v=>v!==null))await d.locator('summary').click();await btn(s,'填入本场景示例作答').click();await expect(s.getByLabel('答案和思路',{exact:true})).not.toHaveValue('');await btn(s,'提交答案').click();}
async function newTest(kind){await s.getByRole('button',{name:'📖 教材',exact:true}).click();await s.locator('.chapter-row').filter({hasText:'按比例增加后的数量'}).getByRole('button',{name:'检测',exact:true}).click();await btn(s,'准备本次检测').click();if(!await s.getByLabel('表现样例',{exact:true}).isVisible())await s.getByText('Mock 场景选择',{exact:true}).click();await s.getByLabel('表现样例',{exact:true}).selectOption(kind);await btn(s,'开始检测').click();}
const task='/admin/#/domain?domain=DOM-MATH&filter=task&id=fraction';
try{
  await a.goto(base+task);await tab(a,'方法').click();await expect(a.locator('main')).toContainText('先');await shot(a,'F01','任务关联两种方法');
  await tab(a,'知识').click();await shot(a,'F02','知识按方法递归汇总');
  await a.goto(base+'/admin/#/evaluation?id=CLAIM-FRACTION&tab=aspects');await expect(tab(a,'评价方面')).toHaveAttribute('aria-selected','true');await shot(a,'F03','同一Task Claim的四方面');
  await a.goto(base+'/admin/#/targets?id=TARGET-MATH');await shot(a,'F04','目标选择Claim并规定要求');
  await a.goto(base+'/admin/#/textbooks?id=BOOK-MATH&chapter=CH-INCREASE&tab=content');await btn(a,'记录核对结果').click();await a.getByRole('dialog').getByLabel('核对结果').selectOption('true');await a.getByRole('dialog').getByLabel('核对依据与疑点').fill('本轮自编样例：原长80米增加四分之一；两种方法均允许，图示用于限定的迁移观察。');await btn(a,'保存').click();await btn(a,'应用更新').click();await shot(a,'F05','核对内容并应用课程');
  await a.goto(base+task);await tab(a,'实例').click();await btn(a,'生成题目').click();await btn(a,'生成候选题').click();await shot(a,'F06','题面参数答案先检查再保存',a.getByRole('dialog'));await btn(a,'检查并保存').click();
  await s.goto(base+'/student/');await s.locator('.space-trigger').click();await btn(s,'＋ 新建学习空间').click();await shot(s,'F07','学生选用管理员准备的教材目标',s.getByRole('dialog'));await btn(s,'创建学习空间').click();
  await s.locator('.chapter-row').filter({hasText:'按比例增加后的数量'}).getByRole('button',{name:'讲解',exact:true}).click();await expect(s.locator('.flow-lesson')).toContainText('80 + 20 = 100 米');await shot(s,'F08','同一对话内讲解原量增加量与总量');
  await btn(s,'可以直接乘四分之五吗？').click();await expect(s.locator('.flow-lesson')).toContainText('80 × 5/4 = 100 米');await shot(s,'F09','追问另一种解法就地补充');
  await btn(s,'准备检测').click();await s.getByText('Mock 场景选择',{exact:true}).click();await s.getByLabel('题目准备样例').selectOption('failed');await btn(s,'开始检测').click();await expect(s.getByRole('alert')).toContainText('检测还没有开始');assert.equal((await state()).uses.filter(u=>u.purpose==='检测').length,0);await shot(s,'F10','准备失败保留学习且未开始检测');await btn(s,'重新准备').click();
  await expect(s.locator('.question-title')).toContainText('第 1/2 题');await expect(s.locator('textarea:visible')).toHaveCount(1);await shot(s,'F11','保存题目后展示并在底部作答');await sample();
  await expect(s.locator('.question-title')).toContainText('第 2/2 题');await expect(s.locator('.result-card')).toHaveCount(0);await shot(s,'F12','图示检测保留页面与对话');await sample();
  await expect(s.locator('.result-card')).toContainText('1 题判为正确');await expect(s.locator('[data-aspect="transfer"]')).toContainText('本次发现不足');await s.locator('[data-aspect="understanding"] summary').click();await shot(s,'F13','作答证据与能力判断及目标结果');
  const firstState=await state(),activity=firstState.lessons[0],uses=firstState.uses.filter(u=>u.activityId===activity.id&&u.purpose==='检测');
  assert.equal(uses.length,2);assert.equal(activity.testQuestions.length,2);assert.ok(uses.every(u=>u.question.checkedAt&&firstState.questions.some(q=>q.id===u.question.id)));checks.push('题目先检查保存、快照采用、同源作答按方面解释、上文保留不冒充独立');
  await btn(s,'查看学习情况').click();await s.locator('.chapter-toggle:visible').filter({hasText:'按比例增加后的数量'}).click();await expect(s.locator('.static-pane [data-requirement="REQ-F3"]')).toContainText('需加强');await shot(s,'F14','学习情况与本次评价使用相同依据');
  await a.goto(base+'/admin/#/activity?id='+activity.id);await tab(a,'评价结果').click();await expect(a.locator('[data-aspect="transfer"]')).toContainText('本次发现不足');await shot(a,'F15','管理员查看同一Claim与作答依据');
  await tab(a,'交互过程').click();await btn(a,'3 · 检测').click();await btn(a,'作废本题评价依据').click();await a.getByRole('dialog').getByLabel('错误原因').fill('走查注入的题目缺陷：假设本题展示的新增段标注有误，已确认不能用于评价。');await shot(a,'F16','作废前说明精确题目版本及影响',a.getByRole('dialog'));await btn(a,'确认作废依据').click();
  await expect(s.locator('.result-card')).toContainText('已排除作废依据');await expect(s.locator('.static-pane [data-requirement="REQ-F3"]')).not.toContainText('需加强');await expect(s.locator('.static-pane [data-requirement="REQ-F2"]')).toContainText('本次能说明');await shot(s,'F17','撤回错误依据保留其他表现');
  const corrected=await state();assert.deepEqual(corrected.uses,firstState.uses);assert.equal(corrected.corrections.length,1);checks.push('纠错不改原作答、不污染其他证据、不计入当前负面评价');
  await a.goto(base+task);await tab(a,'实例').click();await a.getByLabel('来源',{exact:true}).selectOption('学习中生成');await expect(a.locator('.instance-table')).toContainText('已停用');await shot(a,'F18','题库保留停用版本与使用记录');
  await a.getByRole('button',{name:'编辑实例 '+uses[1].question.id,exact:true}).click();await a.getByRole('dialog').getByLabel('题目内容').fill(uses[1].question.question+'（标注核对后的新版）');await btn(a,'检查并保存').click();assert.equal((await state()).questions.find(q=>q.id===uses[1].question.id).version,2);assert.equal((await state()).uses.find(u=>u.id===uses[1].id).question.version,1);checks.push('修订题目产生新版且原展示快照保持v1');
  await newTest('bare');await sample();await sample();await expect(s.locator('[data-aspect="understanding"]')).toContainText('没有足够的解释依据');checks.push('仅答案正确不推断理解');
  await newTest('supported');await s.getByLabel('答案和思路',{exact:true}).fill('任意输入，不属于预设样例');await btn(s,'提交答案').click();await s.getByLabel('答案和思路',{exact:true}).fill('任意输入');await btn(s,'提交答案').click();await expect(s.locator('.result-card')).toContainText('0 题判为正确');checks.push('自由输入不冒充语义判定');
  await newTest('supported');await sample();await sample();await expect(s.locator('.result-card')).toContainText('2 题判为正确');await expect(s.locator('[data-aspect="retention"]')).toContainText('没有延迟后的表现');await s.locator('[data-aspect="independent"] summary').click();await expect(s.locator('[data-aspect="independent"]')).toContainText('本次未先讲解');checks.push('方法B合法且全对仍不证明保持，直接检测不捏造已获讲解');
  await newTest('mixed');await s.getByLabel('答案和思路',{exact:true}).fill('还没提交的草稿');await s.reload();await expect(s.getByLabel('答案和思路',{exact:true})).toHaveValue('还没提交的草稿');await btn(s,'结束并求助').click();await expect(s.locator('.result-card')).toContainText('0/2');checks.push('刷新恢复草稿，求助结束整场检测且未作答不判错');
  await s.setViewportSize({width:1024,height:768});assert.ok(await s.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await expect(s.locator('.static-pane')).toBeVisible();checks.push('平板尺寸保留V2左右布局');
  assert.deepEqual(errors,[]);assert.equal(modelCalls,0);completed=true;
}catch(e){await a.screenshot({path:output+'/admin-failure.png'});await s.screenshot({path:output+'/student-failure.png'});throw e;}
finally{
  const sourceHashes={};for(const file of ['shared/learning-flow.ts','shared/fraction-assessment.ts','shared/FractionAssessment.vue','student/src/components/FlowLesson.vue','student/src/components/ChatWorkspace.vue','student/src/components/FlowCoursePage.vue','admin/src/components/FlowActivityReview.vue','admin/src/components/TaskInstances.vue','admin/src/workbench/textbook-mock.ts','admin/src/workbench/evaluation-mock.ts','admin/src/workbench/learning-space-mock.ts','tests/capture-fraction-flow.mjs'])sourceHashes[file]=createHash('sha256').update(await readFile(new URL('../'+file,import.meta.url))).digest('hex');
  await writeFile(output+'/capture-manifest.json',JSON.stringify({completed,sourceCommit:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),sourceHashes,modelCalls,errors,checks,captures},null,2)+'\n');await browser.close();await new Promise(r=>server.close(r));
}
