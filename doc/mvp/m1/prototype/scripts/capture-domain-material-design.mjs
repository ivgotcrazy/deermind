// Documentation capture only: fresh browser storage, no model calls or UI changes.
import { chromium, expect } from '@playwright/test';
import { mkdir, copyFile, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createPreviewServer } from './serve.mjs';

const assets=new URL('../../design/assets/domain-material-v0.1/',import.meta.url);
await mkdir(assets,{recursive:true});
const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1500,height:1050},locale:'zh-CN'});
page.setDefaultTimeout(10000);
const manifest=[],errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.route('**/api/**',r=>r.abort());
const btn=name=>page.getByRole('button',{name,exact:true});
const shot=async(name,step)=>{
  await page.evaluate(()=>document.fonts.ready);
  await page.screenshot({path:fileURLToPath(new URL(name+'.png',assets)),animations:'disabled'});
  manifest.push({file:name+'.png',step,route:page.url().split('/admin/')[1],source:'this script, isolated browser',viewport:{width:1500,height:1050}});
};
try {
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/domain');
  await btn('新建领域').click();await page.getByLabel('领域名称',{exact:true}).fill('小学数学');await page.getByLabel('覆盖范围',{exact:true}).fill('小学阶段的数学任务、方法和知识');
  await shot('D01-create-domain','M1-D02-S01');await btn('创建并进入').click();await expect(page.getByRole('heading',{name:'小学数学',exact:true})).toBeVisible();
  await shot('D02-empty-domain','M1-D02-S01');
  await page.getByRole('navigation',{name:'后台导航'}).getByRole('button',{name:/教材管理/}).click();
  await btn('导入教材').click();await page.getByLabel('教材名称',{exact:true}).fill('北师大六年级上册 · 本轮核对样例');
  await shot('T01-import-domain','M1-D01-S01');
  await page.getByLabel('所属领域',{exact:true}).selectOption({label:'小学数学'});
  await btn('载入真实教材书页').click();await expect(page.locator('.upload-files tbody tr')).toHaveCount(5);
  await shot('T02-batch-pages','M1-D01-S02');
  await btn('上传并开始整理').click();await expect(page.locator('.material-contents')).toBeVisible();
  await shot('T03-parsed-chapter','M1-D01-S03');
  await page.locator('.element-title').first().click();await shot('T04-element-detail','M1-D01-S04');
  await btn('查看原页').click();await page.locator('.original-preview img').evaluate(img=>img.decode());await shot('T05-source-page','M1-D01-S04');await btn('取消').click();
  // Return to the table through navigation, leaving source and draft intact.
  await page.getByRole('navigation',{name:'后台导航'}).getByRole('button',{name:/教材管理/}).click();
  await shot('T06-textbook-list','M1-D01-S01');
  await page.getByRole('button',{name:/删除导入/}).first().click();await shot('T07-delete-import','M1-D01-S09');await btn('取消').click();
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/domain');
  await btn('载入示例领域').click();await btn('打开示例 k8s').click();
  const k8s=await page.evaluate(()=>{const d=JSON.parse(localStorage.getItem('deermind-m1-domain-v1'));const domain=d.domains.find(x=>x.exampleKey==='k8s'),task=d.tasks.find(x=>x.domainId===domain.id);return {domain:domain.id,method:task.methods[0]};});
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/domain?'+new URLSearchParams({domain:k8s.domain,kind:'solution',id:k8s.method}));
  await expect(page.locator('#method-ending')).toHaveCount(1);
  await page.locator('#method-ending').scrollIntoViewIfNeeded();await expect(page.locator('#method-ending')).toBeInViewport();
  await shot('D14-method-ending','M1-D02-S04');
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/domain');await btn('载入示例领域').click();await btn('打开示例 primary').click();
  const primary=await page.evaluate(()=>{const d=JSON.parse(localStorage.getItem('deermind-m1-domain-v1'));const domain=d.domains.find(x=>x.exampleKey==='primary'),task=d.tasks.find(x=>x.domainId===domain.id);return {domain:domain.id,task:task.id};});
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/domain?'+new URLSearchParams({domain:primary.domain,kind:'task',id:primary.task,tab:'instances'}));
  await btn('新建题目').click();await btn('检查并保存为可用题').click();
  await page.getByRole('alert').scrollIntoViewIfNeeded();await expect(page.getByRole('alert')).toBeInViewport();
  await shot('D10-instance-check','M1-D02-S06');
} finally {await browser.close();await new Promise(r=>server.close(r));}

// These screenshots are emitted by the current active browser regression tests.
const copies=[
 ['domain/05-domain-tasks','D03-task-list','M1-D02-S02'],
 ['domain/06-task-definition','D04-task-definition','M1-D02-S02'],
 ['domain/07-task-methods','D05-task-methods','M1-D02-S03'],
 ['domain/08-task-knowledge','D06-task-knowledge','M1-D02-S03'],
 ['domain/11-prerequisite-list','D07-kc-prerequisites','M1-D02-S05'],
 ['domain/04-instances','D08-instances','M1-D02-S06'],
 ['domain/02-student-question','D09-question-preview','M1-D02-S06'],
 ['solution-template/junior-parent','D11-recursive-method','M1-D02-S04'],
 ['solution-template/senior-all-cases','D12-method-cases','M1-D02-S04'],
 ['solution-template/k8s-recheck','D13-method-recheck','M1-D02-S04'],
 ['task-template/junior-requirements','D15-junior-task','M1-D02-S02'],
 ['task-template/senior-variables','D16-senior-task','M1-D02-S02'],
 ['task-template/k8s-variables','D17-k8s-task','M1-D02-S02'],
 ['material-flow/01-parsed-solutions','T08-separated-solutions','M1-D01-S05'],
 ['material-flow/05-reparse-chart','T09-reparse-preview','M1-D01-S05'],
 ['material-flow/07-row-actions','T10-intake-actions','M1-D01-S06'],
 ['material-flow/08-extract-template','T11-extract-template','M1-D01-S07'],
 ['material-flow/09-partial-completion','T12-partial-intake','M1-D01-S07'],
 ['material-flow/04-intake-complete','T13-intake-complete','M1-D01-S07'],
 ['material-flow/10-add-chapter-link','T14-add-chapter-link','M1-D01-S08'],
 ['material-flow/11-edit-chapter-link','T15-edit-chapter-link','M1-D01-S08'],
 ['material-flow/03-chapter-links','T16-chapter-links','M1-D01-S08'],
 ['intake-dialog/process','T17-add-knowledge','M1-D01-S07'],
];
for(const [from,name,step] of copies){
  const source=new URL('../test-results/'+from+'.png',import.meta.url);
  await copyFile(source,new URL(name+'.png',assets));
  manifest.push({file:name+'.png',step,source:'prototype/test-results/'+from+'.png',capture:'active regression suite, fresh browser; see tests for exact route and viewport'});
}
for(const entry of manifest)entry.sha256=createHash('sha256').update(await readFile(new URL(entry.file,assets))).digest('hex');
await writeFile(new URL('capture-manifest.json',assets),JSON.stringify({capturedAt:new Date().toISOString(),mock:true,modelCalls:0,errors,script:'prototype/scripts/capture-domain-material-design.mjs',screens:manifest},null,2));
if(errors.length)throw new Error(errors.join('\n'));
console.log('Captured '+manifest.length+' documentation screenshots');
