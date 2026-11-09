import { createRequire } from 'node:module';
import { fileURLToPath,pathToFileURL } from 'node:url';
import path from 'node:path';
import { mkdir,readFile,writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const batch=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(batch,'../../../../..');
const project=path.join(root,'doc/mvp/m1/prototype'),assets=path.join(root,'doc/mvp/m1/design/assets/material-assistant-v0.1');
const require=createRequire(path.join(project,'package.json'));
const {chromium,expect}=require('@playwright/test');
const {createPreviewServer}=await import(pathToFileURL(path.join(project,'scripts/serve.mjs')));
await mkdir(assets,{recursive:true});
const baseline=JSON.parse(await readFile(path.join(batch,'baseline.json'),'utf8'));
const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({headless:true}),context=await browser.newContext({viewport:{width:1500,height:1120}}),page=await context.newPage();
page.setDefaultTimeout(10000);const errors=[],calls=[],captures=[];
page.on('pageerror',e=>errors.push(e.message));await context.route('**/api/**',r=>{calls.push(r.request().url());return r.abort();});
const btn=name=>page.getByRole('button',{name,exact:true});
const data=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-import-v1'))[0]);
const card=()=>page.locator('.candidate-card').last();
const send=async text=>{await page.getByLabel('给教材助手的消息').fill(text);await btn('发送').click();};
async function shot(id,step,description,selector){
  await page.locator('.page-container').evaluate(el=>el.scrollTop=0);await page.evaluate(()=>document.fonts.ready);
  const file=id+'.png',target=selector?page.locator(selector):page;await target.screenshot({path:path.join(assets,file),...(selector?{}:{fullPage:true})});
  captures.push({id,file,step,description,url:page.url().replace(/http:\/\/127\.0\.0\.1:\d+/,'http://127.0.0.1:5182'),viewport:page.viewportSize(),selector:selector||null,sha256:createHash('sha256').update(await readFile(path.join(assets,file))).digest('hex')});
}
async function chapter(ch){const d=await data();await page.evaluate(hash=>location.hash=hash,'/textbooks?'+new URLSearchParams({source:d.id,chapter:ch,view:'content'}));}
try{
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/textbooks');await btn('导入教材').click();await btn('载入四例核对样例').click();await shot('TA01','M1-D01-S02','必选领域与批量样例；四例创建独立mock领域');
  await btn('上传并开始整理').click();await expect(page.locator('.material-assistant')).toBeVisible();await shot('TA02','M1-D01-S03','持续对话与章节内容工作区');
  await btn('教材解法 1').click();await btn('请助手修正 教材解法 1').click();await page.getByLabel('给教材助手的消息').fill('这里是两种解法，请分别提取。');await shot('TA03','M1-D01-S05','引用具体解法并输入修正要求');
  await btn('发送').click();await expect(page.locator('.candidate-preview .parsed-element-view')).toHaveCount(2);await shot('TA04','M1-D01-S06','一条合并解法成为两条候选，尚未采用');
  await btn('查看原页').click();await page.locator('.candidate-preview img').evaluate(img=>img.decode());await shot('TA05','M1-D01-S04/S06','打开原页核对，公式结果仍只读');await btn('收起原页').click();
  await card().getByRole('button',{name:'继续修正',exact:true}).click();await send('请再核对两个解法的公式和单位');await expect(page.locator('.candidate-card').first()).toContainText('已由后续候选替代');await page.reload();await card().getByRole('button',{name:'查看结果',exact:true}).click();await shot('TA06','M1-D01-S06','连续修正后保留历史候选；刷新可继续查看');
  await card().getByRole('button',{name:'采用结果',exact:true}).click();await expect(card()).toContainText('已采用');await shot('TA07','M1-D01-S07','明确采用后更新解析内容，不自动入库');
  await btn('返回内容列表').click();await btn('教材解法 2').click();await page.getByLabel('选择 逐层求出人数',{exact:true}).check();await page.getByLabel('选择 先合并两层比例',{exact:true}).check();await btn('提交到领域').click();await page.getByRole('link',{name:/领域待入库/}).click();await expect(page.locator('.domain-intake')).toBeVisible();await shot('TA08','M1-D01-S07→M1-D02','题目与两条解法进入原有领域待入库流程');
  for(const key of await page.locator('.intake-list tbody tr').evaluateAll(rows=>rows.map(r=>r.dataset.element))){
    const row=page.locator('.intake-list [data-element="'+key+'"]'),kind=await row.getByRole('button',{name:'关联任务模板',exact:true}).count()?'任务':'解法';
    await row.getByRole('button',{name:'提取'+kind+'模板',exact:true}).click();await btn('保存模板').click();await row.getByRole('button',{name:'关联'+kind+'模板',exact:true}).click();await btn('确认关联').click();
  }
  await page.getByRole('link',{name:'返回教材章节 →',exact:true}).click();await btn('添加关联').click();const select=page.getByRole('dialog').getByLabel('任务模板',{exact:true});const taskId=await select.locator('option').nth(1).getAttribute('value');await select.selectOption(taskId);await shot('TA09A','M1-D01-S08','添加章节关联，明确选择任务及本章方法');await btn('保存').click();await expect(page.locator('.chapter-links tbody tr')).toHaveCount(1);await shot('TA09','M1-D01-S08','回教材显式关联章节任务及采用方法，KC汇总显示');await page.locator('.chapter-links').getByRole('button',{name:'编辑',exact:true}).click();await shot('TA09B','M1-D01-S08','章节方法仍在独立关联弹框中选择，不是解析结果编辑器');await btn('取消').click();
  await chapter('统计图');await btn('请助手修正 三种统计图与教学提示').click();await send('请补齐原题里的三张统计图');await expect(page.locator('.candidate-preview svg')).toHaveCount(3);await page.setViewportSize({width:1500,height:2200});await shot('TA10','M1-D01-S06','完整三张统计图、数据与单位的候选渲染','.candidate-preview');await page.setViewportSize({width:1500,height:1120});await card().getByRole('button',{name:'不采用',exact:true}).click();await shot('TA11','M1-D01-S07','不采用候选，旧解析结果保持');await btn('返回内容列表').click();
  await send('模拟处理失败');await expect(page.locator('.assistant-message').last()).toContainText('读取失败');await shot('TA12','M1-D01-S06','处理失败保留内容，提供重试');await btn('重试').click();await expect(page.locator('.candidate-preview svg')).toHaveCount(3);
  await chapter('圆');await btn('请助手修正 六种平面图形和原图标记').click();await send('请核对图形和附页');await expect(page.locator('.assistant-message').last()).toContainText('附页没有提供');await shot('TA13','M1-D01-S06','缺失附页先请求材料，不编造可采用结果');
  if(errors.length||calls.length)throw Error(JSON.stringify({errors,calls}));
  await writeFile(path.join(assets,'capture-manifest.json'),JSON.stringify({version:'0.1',capturedAt:new Date().toISOString(),baselineHead:baseline.head,sourceScript:path.relative(root,path.join(batch,'capture.mjs')).replaceAll('\\','/'),data:'Fresh isolated browser; built-in four-case mock and actual UI clicks; no user storage, model calls or manual content edits',sources:baseline.prototypeSources,captures,errors,modelCalls:calls.length},null,2)+'\n');
  await writeFile(path.join(batch,'capture-result.json'),JSON.stringify({result:'passed',screenshots:captures.length,errors,modelCalls:calls.length},null,2)+'\n');
  console.log(JSON.stringify({result:'passed',screenshots:captures.length,errors,modelCalls:calls.length}));
} finally{await browser.close();await new Promise(r=>server.close(r));}
