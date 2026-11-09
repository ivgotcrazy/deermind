import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const root=fileURLToPath(new URL('../../../../../',import.meta.url));
const prototype=path.join(root,'doc/mvp/m1/prototype');
const require=createRequire(path.join(prototype,'package.json'));
const {chromium,expect}=require('@playwright/test');
const {createPreviewServer}=await import(pathToFileURL(path.join(prototype,'scripts/serve.mjs')));
const out=path.join(root,'doc/mvp/m1/design/assets/evaluation-trace-v0.1');
await mkdir(out,{recursive:true});
const server=createPreviewServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1100},locale:'zh-CN'});
const page=await context.newPage();const errors=[],calls=[],captures=[];
page.on('pageerror',e=>errors.push(e.message));
await context.route('**/api/**',r=>{calls.push(r.request().url());return r.abort();});
const go=query=>page.goto(`http://127.0.0.1:${server.address().port}/admin/#/learning-spaces${query?'?'+query:''}`);
const btn=name=>page.getByRole('button',{name,exact:true});
const dialog=()=>page.getByRole('dialog');
const db=name=>dialog().getByRole('button',{name,exact:true});
async function shot(id,step,description){
  await page.evaluate(()=>document.fonts.ready);
  const bytes=await page.screenshot({path:path.join(out,id+'.png'),animations:'disabled'});
  captures.push({id,step,description,file:id+'.png',route:new URL(page.url()).hash,sha256:createHash('sha256').update(bytes).digest('hex')});
}
try{
  await go('');await expect(btn('进入 LS-001')).toBeVisible();await shot('EV01','M1-D06-E01','学习空间列表：学生、课程和采用目标');
  await btn('进入 LS-001').click();await shot('EV02','M1-D06-E02','按方法和方面查看目标结果');
  await btn('先求增加量，再求新量 · 独立 · 需加强').click();await expect(dialog().locator('.goal-evidence-list tbody tr')).toHaveCount(3);await shot('EV03','M1-D06-E03','当前 Belief 与三条累计有效 Evidence');
  await db('查看 R1 Evidence').click();await expect(btn('学习目标')).toHaveAttribute('aria-current','page');await shot('EV04','M1-D06-E04','单条 Evidence：判据、依据片段及三个来源事件');
  await db('120 本书：提交 150 本并解释').click();await expect(btn('学习目标')).toHaveAttribute('aria-current','page');await shot('EV05','M1-D06-E05','来源事件：原始作答及帮助，保持学习目标上下文');
  await db('← 返回目标依据').click();await btn('关闭对话框').click();
  await btn('先求增加量，再求新量 · 保持 · 需加强').click();await dialog().locator('.replaced-evidence summary').click();await shot('EV06','M1-D06-E06','纠正后有效证据与折叠的历史证据分开');
  await db('R3 · 支持 · 已被替代').click();await shot('EV07','M1-D06-E06','旧 Evidence 留存，明确被替代并可定位新解释');
  await go('id=LS-001&tab=events&category=评价与系统');await shot('EV08','M1-D06-E07','空间事件中的评价处理留痕');
  await go('id=LS-001&tab=events&event=LS-001-020B');await expect(dialog().locator('.belief-changes')).toContainText('77.3% → 16.7%');await shot('EV09','M1-D06-E08','Belief 更新事件：实际前后值与重算基线');
  await go('id=LS-001&tab=events&event=LS-001-018');await shot('EV10','M1-D06-E09','目标历史事件保留当时通过，当前状态已经需加强');
  await go('id=LS-001');await btn('按原量的 5/4 倍计算 · 独立 · 待确认').click();await shot('EV11','M1-D06-E10','未使用方法没有 Evidence，不显示先验为能力');
  await go('id=LS-001&tab=events&event=LS-001-032');await shot('EV12','M1-D06-E10','评价失败事件：保留作答，不制造新证据或进步');
  expect(errors).toEqual([]);expect(calls).toEqual([]);
  const sources=[];
  for(const rel of ['src/components/LearningSpaceWorkspace.vue','src/model/learning-spaces.ts','tests/learning-spaces.test.mjs']){
    const bytes=await readFile(path.join(prototype,rel));sources.push({path:'doc/mvp/m1/prototype/'+rel,sha256:createHash('sha256').update(bytes).digest('hex')});
  }
  await writeFile(path.join(out,'capture-manifest.json'),JSON.stringify({version:'0.1',capturedAt:new Date().toISOString(),timezone:'Asia/Shanghai',viewport:{width:1440,height:1100},sourceScript:'src/mvp_foundation/m1/design-reviews/20261109-evaluation-trace/capture.mjs',data:'Fixed mock LS-001/LS-002/LS-003, isolated browser; no real evaluation or LLM',sources,captures,errors,apiCalls:calls},null,2));
  console.log(`Captured ${captures.length} screenshots; no API calls or browser errors.`);
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
