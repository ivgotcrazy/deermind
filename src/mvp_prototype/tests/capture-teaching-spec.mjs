import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {chromium,expect} from '@playwright/test';
import {createPrototypeServer} from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../doc/mvp/phase-4-product-and-domain-foundation/assets/product-interaction/teaching-model/',import.meta.url));
await mkdir(output,{recursive:true});
const captures=[],errors=[];let modelCalls=0,completed=false;
const server=createPrototypeServer({directory:output,config:{key:'fixture',model:'mock'},provider:async()=>{modelCalls++;throw Error('No model call expected');}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}/admin/#/interaction`;
const browser=await chromium.launch({headless:true});
const btn=(p,name)=>p.getByRole('button',{name,exact:true});
async function page(){const c=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'});const p=await c.newPage();p.on('pageerror',e=>errors.push(e.message));await p.goto(base);return {c,p};}
async function shot(p,id,title,locator){
  await p.evaluate(()=>document.fonts.ready);
  const original=p.viewportSize();
  // The application scrolls inside page-container; fullPage alone clips that content.
  if(!locator){
    const height=await p.locator('.page-container').evaluate(el=>Math.ceil(el.scrollHeight+el.getBoundingClientRect().top+32));
    await p.setViewportSize({...original,height:Math.max(original.height,height)});
  }
  const bytes=await (locator||p).screenshot({path:output+id+'.png',animations:'disabled',...(!locator?{fullPage:true}:{})});
  captures.push({id,title,route:new URL(p.url()).pathname+new URL(p.url()).hash,file:id+'.png',sha256:createHash('sha256').update(bytes).digest('hex'),viewport:p.viewportSize(),capturedAt:new Date().toISOString()});
  if(!locator)await p.setViewportSize(original);
  console.log(id+' '+title);
}
try{
  const {c,p}=await page(),dialog=()=>p.getByRole('dialog');
  await expect(p.locator('.graph-node')).toHaveCount(6);await shot(p,'T01','教学蓝图与阶段详情');
  await btn(p,'编辑阶段').click();await shot(p,'T02','编辑阶段职责及策略引用',dialog());await btn(p,'取消').click();
  await btn(p,'添加阶段').click();await dialog().getByLabel('阶段名称',{exact:true}).fill('比较方法的条件');await dialog().getByLabel('阶段目的',{exact:true}).fill('说明两种方法各在什么条件下适用。');await dialog().getByLabel('需要的信息',{exact:true}).fill('本次任务、两种方法及学生的实际回应。');await dialog().getByLabel('留下的结果',{exact:true}).fill('学生对两种方法适用条件的说明。');await shot(p,'T03','添加阶段并指定插入连接',dialog());await btn(p,'取消').click();
  await p.getByRole('button',{name:'连接：确定学习起点 → 讲解与互动，需要讲解',exact:true}).locator('text').click();await btn(p,'编辑连接').click();await shot(p,'T04','编辑连接条件与判断依据',dialog());await btn(p,'取消').click();
  await btn(p,'添加连接').click();await shot(p,'T05','添加分支连接',dialog());await btn(p,'取消').click();
  await p.getByRole('button',{name:'阶段 3：讲解与互动',exact:true}).click();await btn(p,'编辑阶段').click();await dialog().getByLabel('阶段目的',{exact:true}).fill('');await btn(p,'应用到草稿').click();await expect(dialog().getByRole('alert')).toBeVisible();await shot(p,'T06','缺少阶段目的时保留输入并提示',dialog());
  await dialog().getByLabel('阶段目的',{exact:true}).fill('先讲清当前关键关系，再根据实际回应决定下一步。');await btn(p,'应用到草稿').click();await shot(p,'T07','阶段修改进入蓝图草稿');await btn(p,'保存蓝图').click();await btn(p,'修改记录').click();await shot(p,'T08','保存后的模型版本与修改记录',dialog());await btn(dialog(),'关闭对话框').click();
  await btn(p,'情境推演').click();await shot(p,'T09','模型修改后旧情境明确待核对');await btn(p,'← 返回教学蓝图').click();
  await p.getByRole('navigation',{name:'教学模型分区'}).getByRole('button',{name:'教学策略',exact:true}).click();await shot(p,'T10','策略列表及阶段引用');await btn(p,'对比辨析').click();await shot(p,'T11','完整对比辨析策略');await btn(p,'编辑调整与结束').click();await shot(p,'T12','分区编辑策略',dialog());await btn(p,'取消').click();
  await btn(p,'停用策略').click();await shot(p,'T13','停用策略后保留引用并说明限制');
  await p.getByRole('navigation',{name:'教学模型分区'}).getByRole('button',{name:'通用规则',exact:true}).click();await p.locator('.system-boundaries summary').click();await shot(p,'T14','通用规则与只读系统约束');await btn(p,'编辑规则：按当前目标和表现选择').click();await shot(p,'T15','编辑通用规则的要求及依据',dialog());await btn(p,'取消').click();await c.close();
  const second=await page(),s=second.p;await btn(s,'情境推演').click();await btn(s,'下一轮').click();await shot(s,'T16','基础含义不清楚时选择回补');await btn(s,'下一轮').click();await shot(s,'T17','回补后根据表现选择下一步');
  await btn(s,'会算但解释不清').click();await btn(s,'下一轮').click();await shot(s,'T18','会算但理由不足时选择对比辨析');await btn(s,'仍认为两种说法相同 →').click();await shot(s,'T19','同一阶段内切换为概念回补');
  await btn(s,'展开蓝图路径与来源规则').click();await s.getByRole('button',{name:'连接：确定学习起点 → 讲解与互动，需要讲解',exact:true}).locator('text').click();await shot(s,'T20','实际所选路径与原版本转移规则',s.locator('.scene-graph'));await btn(s,'收起蓝图路径与来源规则').click();
  await btn(s,'已理解，检验迁移').click();await btn(s,'下一轮').click();await shot(s,'T21','跳过重复讲解并进入图示检测');await btn(s,'请求讲解，先结束检测 →').click();await shot(s,'T22','求助结束检测后转入讲解');await btn(s,'上一轮').click();await btn(s,'图示存在歧义 →').click();await shot(s,'T23','材料歧义保留未决而不归因于学生');await btn(s,'上一轮').click();await btn(s,'12 平方米，并解释清楚 →').click();await shot(s,'T24','检测成功后的有限结论与收束');
  await second.c.close();assert.deepEqual(errors,[]);assert.equal(modelCalls,0);assert.equal(captures.length,24);completed=true;
}finally{
  await browser.close();await new Promise(r=>server.close(r));
  const sourceHashes={};for(const file of ['admin/src/App.vue','admin/src/components/TeachingWorkspace.vue','admin/src/components/TeachingBlueprint.vue','admin/src/workbench/teaching-mock.ts','tests/capture-teaching-spec.mjs'])sourceHashes[file]=createHash('sha256').update(await readFile(new URL('../'+file,import.meta.url))).digest('hex');
  await writeFile(output+'capture-manifest.json',JSON.stringify({completed,sourceCommit:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),sourceHashes,buildHashes:{admin:createHash('sha256').update(await readFile(new URL('../admin/dist/index.html',import.meta.url))).digest('hex')},modelCalls,errors,captures},null,2)+'\n');
}
