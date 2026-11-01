import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {chromium,expect as baseExpect} from '@playwright/test';
import {createPrototypeServer} from '../scripts/serve.mjs';
const expect=baseExpect.configure({timeout:15000});
const output=fileURLToPath(new URL('../../../doc/mvp/phase-4-product-and-domain-foundation/assets/product-interaction/student-teaching/',import.meta.url));
await mkdir(output,{recursive:true});
const captures=[],checks=[],errors=[];let modelCalls=0,completed=false;
const server=createPrototypeServer({directory:output,config:{key:'fixture',model:'mock'},provider:async()=>{modelCalls++;throw Error('No model calls allowed');}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({headless:true});
const btn=(p,name)=>p.getByRole('button',{name,exact:true});
async function open(scenario,context='textbook',width=1440){const c=await browser.newContext({viewport:{width,height:1000},locale:'zh-CN'});const p=await c.newPage();p.setDefaultTimeout(15000);p.on('pageerror',e=>errors.push(e.message));await p.goto(`${base}/student/?teaching=${scenario}&context=${context}`);await expect(p.locator('.teaching-lesson')).toBeVisible();return {c,p};}
async function shot(p,id,title){await p.evaluate(()=>document.fonts.ready);await p.locator('.messages-container').evaluate(el=>el.scrollTo({top:el.scrollHeight,behavior:'instant'}));const bytes=await p.screenshot({path:output+id+'.png',animations:'disabled'});captures.push({id,title,file:id+'.png',route:new URL(p.url()).pathname+new URL(p.url()).search,sha256:createHash('sha256').update(bytes).digest('hex'),viewport:p.viewportSize()});console.log(id+' '+title);}
async function sample(p,start){await btn(p,'演示工具').click();const d=p.getByRole('dialog',{name:'演示工具'});await d.getByRole('button',{name:new RegExp('^'+start)}).click();await btn(p,'提交作答').click();}
async function tool(p,name){await btn(p,'演示工具').click();await p.getByRole('dialog').getByRole('button',{name,exact:true}).click();}
async function stored(p,scenario){return p.evaluate(s=>JSON.parse(sessionStorage.getItem('deermind-teaching-preview-v1-'+s)),scenario);}
async function start(p){await btn(p,'准备题目').click();await btn(p,'开始检测').click();}
try{
  let {c,p}=await open('foundation');
  await expect(p.locator('textarea')).toHaveCount(1);await expect(p.locator('.dot-groups>div')).toHaveCount(3);await shot(p,'S01','基础含义疑问先回补，保留教材上下文');
  await sample(p,'18 ÷ 3');await shot(p,'S02','局部练习后回到原问题');
  await sample(p,'摄影有4人');await expect(btn(p,'用新题检测')).toBeVisible();await shot(p,'S03','原题理解后选择下一步');
  await btn(p,'用新题检测').click();await shot(p,'S04','检测说明与学生同意');await start(p);
  await expect(p.locator('.mode-text')).toContainText('检测中');await shot(p,'S05','未展示解法的新文字题与统一作答框');
  await p.locator('textarea').fill('30 × 2/5');await p.reload();await expect(p.locator('textarea')).toHaveValue('30 × 2/5');
  await sample(p,'30 × 2/5');await expect(p.locator('.teaching-lesson')).toContainText('本次检测已结束');await shot(p,'S06','提交后结束检测并反馈');
  await btn(p,'查看本次小结').click();await p.getByText('查看判断依据与学习要求',{exact:true}).click();await shot(p,'S07','按实际经历小结，四方面展开查看');
  let state=await stored(p,'foundation');assert.equal(state.attempts.filter(a=>a.purpose==='检测').length,1);assert.equal(state.explanationSupported,true);assert.equal(state.transferSupported,false);checks.push('A：回补、回原题、自愿检测、提交反馈、草稿刷新与有限评价');await c.close();
  ({c,p}=await open('foundation'));await sample(p,'三分之一');await expect(p.locator('.teaching-lesson')).toContainText('不急着再做一道相同的题');await shot(p,'S08','基础仍不清楚时更换表示而不无限刷题');await btn(p,'今天先到这里').click();state=await stored(p,'foundation');assert.equal(state.checks,0);assert.equal(state.explanationSupported,false);checks.push('基础仍困惑可结束，不虚构完整任务检测');await c.close();
  ({c,p}=await open('foundation'));await sample(p,'18 ÷ 3');await sample(p,'航模是12人');await expect(p.locator('.comparisons')).toBeVisible();checks.push('原题第二层混淆转入对比，同一对话继续');await c.close();
  ({c,p}=await open('explanation','status'));await expect(p.locator('.static-pane h2:visible')).toHaveText('学习情况');await shot(p,'S09','正确答案但理由不足，先对比参照量');
  await sample(p,'都是');await shot(p,'S10','同一对话切回基础回补');await btn(p,'直接讲解').click();await btn(p,'试一道练习').click();await sample(p,'24 × 1/3');await shot(p,'S11','新文字练习即时反馈');await btn(p,'今天先到这里').click();state=await stored(p,'explanation');assert.equal(state.checks,0);assert.equal(state.explanationSupported,false);checks.push('B：对比→回补→练习，受助表现不当独立掌握');await c.close();
  ({c,p}=await open('explanation'));await btn(p,'直接讲解').click();await expect(p.locator('.teaching-lesson')).toContainText('A 的四分之三以摄影组4人为整体');await shot(p,'S12','学生直接求助时立即解释');await btn(p,'试一道练习').click();await sample(p,'24 × 1/3');await btn(p,'用新题检测').click();await start(p);await expect(p.locator('.teaching-lesson')).toContainText('30本书');checks.push('直接解释及练习后新题，未复用已讲过题当新题');await c.close();
  ({c,p}=await open('transfer'));await shot(p,'S13','已有文字理解，跳过重复讲解');await start(p);await expect(p.locator('.teaching-lesson')).not.toContainText('24平方米');await expect(p.locator('.teaching-lesson')).not.toContainText('12平方米');await shot(p,'S14','图示检测不泄露中间量和答案');
  await btn(p,'放大图示').click();await shot(p,'S15','放大原图保持内容不变');await btn(p,'关闭图示').click();await sample(p,'40 × 3/5');await btn(p,'查看本次小结').click();await p.getByText('查看判断依据与学习要求',{exact:true}).click();await shot(p,'S16','图示成功只增加本类图示支持，保留既有文字判断');state=await stored(p,'transfer');assert.equal(state.transferSupported,true);checks.push('C：检测自愿开始、无泄答、图示有限支持及既有认识保留');await c.close();
  ({c,p}=await open('transfer'));await start(p);await sample(p,'40 × 1/2');await shot(p,'S17','图示错误在检测结束后反馈');const before=(await stored(p,'transfer')).attempts;await btn(p,'讲讲这里').click();assert.deepEqual((await stored(p,'transfer')).attempts,before);await shot(p,'S18','检测后讲解不覆盖原作答');checks.push('错误反馈与后续讲解分开，原作答不改写');await c.close();
  ({c,p}=await open('transfer'));await start(p);await sample(p,'12$');await expect(p.locator('.teaching-lesson')).toContainText('数值正确');await shot(p,'S19','只有数值时理解仍待确认');state=await stored(p,'transfer');assert.equal(state.transferSupported,false);checks.push('只写正确数值不判解释充分');await c.close();
  ({c,p}=await open('transfer'));await start(p);await p.locator('textarea').fill('我先看左边');await btn(p,'求助并结束检测').click();await shot(p,'S20','求助先结束检测，未提交不计错');state=await stored(p,'transfer');assert.equal(state.attempts[0].answer,'');assert.match(state.attempts[0].help,/我先看左边/);assert.equal(state.testFinished,true);checks.push('求助先结束，草稿保留，未提交不计错');await c.close();
  ({c,p}=await open('transfer'));await start(p);await btn(p,'图示看不清').click();assert.equal((await stored(p,'transfer')).step,'testing');await shot(p,'S21','看不清先查看材料，不自动推断能力不足');await tool(p,'模拟已确认的材料缺陷');await shot(p,'S22','确有材料缺陷时停止判定');assert.equal((await stored(p,'transfer')).transferSupported,false);checks.push('主观看不清与确认材料缺陷分开');await c.close();
  ({c,p}=await open('transfer'));await tool(p,'模拟题目准备失败');await expect(btn(p,'开始检测')).toHaveCount(0);await shot(p,'S23','题目准备失败时不开始检测');await btn(p,'重试准备').click();await btn(p,'开始检测').click();await p.locator('textarea').fill('这是没有预写的回答');await btn(p,'提交作答').click();await shot(p,'S24','未覆盖自由输入不套用预写评价');state=await stored(p,'transfer');assert.equal(state.step,'feedback');assert.equal(state.attempts[0].result,'未预设判定');checks.push('准备失败可重试，未知回答保留未决');await c.close();
  ({c,p}=await open('transfer','textbook',1024));await p.setViewportSize({width:1024,height:768});await start(p);await p.locator('textarea').fill('草稿');await btn(p,'▼ 收起').click();await btn(p,'▲ 展开').click();await expect(p.locator('textarea')).toHaveValue('草稿');await expect(p.locator('.static-pane h2:visible')).toHaveText('教材');await shot(p,'S25','平板尺寸仍保留右侧教材及唯一输入框');assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await btn(p,'结束检测').click();await expect(p.locator('.learning-summary')).toContainText('没有判错');checks.push('1024×768、收起展开、右侧保留、无横向溢出与提前结束');await c.close();
  ({c,p}=await open('foundation'));await sample(p,'18 ÷ 3');await tool(p,'重新开始本情境');state=await stored(p,'foundation');assert.equal(state.attempts.length,0);assert.equal(state.step,'basic');assert.equal(state.messages.length,4);await btn(p,'直接讲解').click();await btn(p,'今天先到这里').click();await p.reload();await expect(p.locator('.learning-summary')).toBeVisible();checks.push('重置和结束后刷新，无意外重新开测');await c.close();
  assert.equal(modelCalls,0);assert.deepEqual(errors,[]);completed=true;
}finally{
  await browser.close();await new Promise(r=>server.close(r));
  const sourceHashes={};for(const file of ['student/src/App.vue','student/src/live.ts','student/src/components/ChatWorkspace.vue','student/src/components/InputComposer.vue','student/src/components/TeachingLesson.vue','student/src/components/TeachingCoursePage.vue','student/src/teaching-session.ts','student/public/teaching.html','shared/ChainDiagram.vue','tests/capture-student-teaching.mjs'])sourceHashes[file]=createHash('sha256').update(await readFile(new URL('../'+file,import.meta.url))).digest('hex');
  await writeFile(output+'capture-manifest.json',JSON.stringify({completed,modelCalls,errors,checks,sourceHashes,captures},null,2)+'\n');console.log(JSON.stringify({completed,checks:checks.length,screenshots:captures.length,modelCalls,errors}));
}
