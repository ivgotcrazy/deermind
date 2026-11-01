import assert from 'node:assert/strict';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { chromium, expect } from '@playwright/test';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../doc/mvp/phase-4-product-and-domain-foundation/assets/product-interaction/student-pages/',import.meta.url));
await mkdir(output,{recursive:true});
let modelCalls=0,completed=false;const captures=[],checks=[],errors=[];
const server=createPrototypeServer({directory:output,config:{key:'fixture',model:'fixed'},provider:async()=>{modelCalls++;throw Error('No LLM in page review');}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true,channel:'msedge'});
const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'});
const p=await context.newPage();p.setDefaultTimeout(9000);p.on('pageerror',e=>errors.push(e.message));
const btn=name=>p.getByRole('button',{name,exact:true});
const nav=async name=>p.locator('.nav-items').getByRole('button',{name}).click();
async function shot(id,title){await p.evaluate(()=>document.fonts.ready);const image=await p.screenshot({path:output+'/'+id+'.png',animations:'disabled'});captures.push({id,title,file:id+'.png',route:new URL(p.url()).pathname+new URL(p.url()).search,page:await p.locator('.student-page:visible h2').first().innerText(),viewport:p.viewportSize(),sha256:createHash('sha256').update(image).digest('hex')});console.log(id+' '+title);}
try {
  await p.goto(base+'/student/?preview=pages');await expect(p.getByRole('heading',{name:'首页',exact:true})).toBeVisible();await shot('P01','首页未填写课堂进度');
  await btn('更新课堂进度').click();await p.getByRole('dialog').getByLabel('比例的应用',{exact:true}).check();await btn('确认').click();await shot('P02','首页课堂进度与继续学习');
  await expect(p.locator('.stats-grid')).toContainText('6 天');await expect(p.locator('.stats-grid')).toContainText('3 次');await expect(p.locator('.stats-grid')).toContainText('2 次');checks.push('6个学习日、3次讲解、2次结束检测由同一组记录计数');
  await btn('全部学习记录 →').click();await shot('P03','从首页进入完整活动记录');await btn('← 返回首页').click();
  await nav('学习');await expect(p.getByLabel('单元',{exact:true})).toHaveValue('第四单元 比例');await expect(p.locator('.learning-status-page:visible')).not.toContainText('65%');await shot('P04','按教材单元查找章节状态');
  await p.locator('.chapter-toggle:visible').filter({hasText:'比例的应用'}).click();await expect(p.locator('.learning-status-page:visible')).toContainText('已达标 3 项');await expect(p.locator('.learning-status-page:visible')).toContainText('需加强 1 项');await expect(p.locator('.learning-status-page:visible')).toContainText('待确认 2 项');await shot('P05','具体要求与三类判断');
  await btn('需加强 1 项').click();await p.locator('[data-requirement="R4"] summary').click();await shot('P06','筛选需加强并展开判断依据');
  await p.locator('[data-requirement="R4"] .evidence button').click();await expect(p.locator('.question-records-page:visible')).toContainText('80 × 1/4 = 20米');await shot('P07','从判断定位原题和作答');
  await btn('查看所属学习活动 →').click();await shot('P08','查看题目所属检测活动');await p.getByRole('dialog').getByRole('button',{name:'关闭',exact:true}).click();await btn('返回判断依据 →').click();await expect(p.locator('[data-requirement="R4"] details')).toHaveAttribute('open','');checks.push('要求→原题→所属活动→返回要求，原筛选与展开状态保留');
  await p.getByLabel('作答日期',{exact:true}).selectOption('7');await expect(p.locator('.answer-statistics:visible')).toContainText('3 / 4 次正确');await btn('查看作答明细与统计口径').click();await p.locator('.answer-statistics:visible').scrollIntoViewIfNeeded();await shot('P09','独立作答统计与排除明细');await p.getByLabel('作答日期',{exact:true}).selectOption('0');await expect(p.locator('.answer-statistics:visible')).toContainText('原作答日期未知');await expect(p.locator('[data-requirement="R4"]')).toContainText('需加强');checks.push('近期统计排除受助与未决；未知日期只在全部；切换日期不改当前要求状态');
  await nav('教材');await p.getByLabel('查找章节',{exact:true}).fill('比例的应用');await expect(p.locator('.textbook-page:visible')).not.toContainText('已掌握');await shot('P10','教材定位与学习范围选择');await btn('阅读材料').click();await shot('P11','材料正文与图示');await btn('← 返回教材目录').click();await p.getByLabel('加入本次检测',{exact:true}).check();await btn('查看检测范围').click();await shot('P12','确认只对本次生效的检测范围');await btn('准备本次检测').click();await expect(p.locator('.chat-pane')).toBeVisible();await expect(p.locator('.textbook-page:visible')).toBeVisible();await shot('P13','从教材进入对话并保留右侧页面');await btn('▼ 收起').click();await expect(p.locator('.textbook-page:visible')).toBeVisible();await btn('▲ 展开').click();checks.push('按次范围传入对话，V2展开收起和右侧来源页面保留');await btn('▼ 收起').click();
  await nav('题目');await btn('← 返回题目列表').click();await btn('全部题目').click();await shot('P14','全量题目按来源与最近作答组织');await btn('错题').click();await expect(p.locator('.question-records-page:visible .list-row')).toHaveCount(2);await p.getByRole('button',{name:'一条绳子原来长48米，增加原长的四分之一后，现在长多少米？',exact:true}).click();await expect(p.locator('.question-records-page:visible')).toContainText('48 + 12 = 60米');await expect(p.locator('.question-records-page:visible .list-row')).toHaveCount(2);await shot('P15','订正后保留原错误与受助条件');checks.push('2道错题按题目去重；订正正确不删历史错误，也不标已掌握');
  await btn('← 返回题目列表').click();await btn('待判定').click();await shot('P16','待判定记录与原日期未知');await btn('未作答').click();await expect(p.locator('.question-records-page:visible .list-row')).toHaveCount(1);checks.push('未作答和待判定都有入口，均不算错题');
  await nav('首页');await btn('继续学习').click();await p.setViewportSize({width:1024,height:768});await shot('P17','平板保留左右对话与首页');assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await p.setViewportSize({width:1440,height:1000});await btn('▼ 收起').click();
  await p.locator('.space-trigger').click();await p.getByRole('button',{name:/语文·六下/}).click();await expect(p.locator('.home-page:visible')).not.toContainText('从图中找出');await nav('学习');await expect(p.locator('.learning-status-page:visible')).toContainText('暂无可统计作答');await shot('P18','其他空间空状态不借用数学判断');checks.push('切换空间隔离学习记录与判断；未知状态不显示0%');
  assert.deepEqual(errors,[]);assert.equal(modelCalls,0);completed=true;
} catch(e){await p.screenshot({path:output+'/failure.png'});throw e;}
finally {
  const sourceHashes={};for(const file of ['student/src/App.vue','student/src/conversation.ts','student/src/components/ConversationPane.vue','student/src/student-pages.ts','student/src/course-page-data.ts','student/src/student-pages.css','student/src/components/StudentPages.vue','student/src/components/HomePage.vue','student/src/components/LearningStatusPage.vue','student/src/components/TextbookPage.vue','student/src/components/ErrorBookPage.vue','student/src/components/ClassroomProgressDialog.vue','student/src/components/ChatWorkspace.vue','tests/capture-student-pages.mjs'])sourceHashes[file]=createHash('sha256').update(await readFile(new URL('../'+file,import.meta.url))).digest('hex');
  await writeFile(output+'/capture-manifest.json',JSON.stringify({completed,sourceCommit:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),sourceHashes,modelCalls,errors,checks,captures},null,2)+'\n');await browser.close();await new Promise(r=>server.close(r));
}
