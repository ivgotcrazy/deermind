import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { expect } from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/material-review/',import.meta.url));
await mkdir(output,{recursive:true});
test('real textbook pages retain teaching structure from organization to student reading',async t=>{
  let modelCalls=0;const server=createPrototypeServer({directory:output,config:{key:'fixture',model:'fixed'},provider:async()=>{modelCalls++;throw Error('No LLM expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const ctx=await browser.newContext({viewport:{width:1600,height:1050},locale:'zh-CN'}),admin=await ctx.newPage(),student=await ctx.newPage();
  const errors=[],posts=[],checks=[];let failed=false;
  for(const p of [admin,student]){p.setDefaultTimeout(10000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});}
  const btn=(name)=>admin.getByRole('button',{name,exact:true}),tree=(name)=>admin.locator('.material-tree-item').filter({has:admin.locator('span',{hasText:name})});
  const state=()=>admin.evaluate(()=>JSON.parse(localStorage.getItem('deermind-next-textbook-import-v1')));
  const edit=(id)=>admin.locator('[data-block="'+id+'"]').getByRole('button',{name:'编辑',exact:true}).click();
  async function check(name,fn){if(failed)return;await t.test(name,async()=>{try{await fn();checks.push({name,passed:true});}catch(e){failed=true;checks.push({name,passed:false});await admin.screenshot({path:output+'/failure.png',fullPage:true});throw e;}});}
  t.after(async()=>{await writeFile(output+'/review.json',JSON.stringify({checks,errors,posts,modelCalls},null,2));await browser.close();await new Promise(r=>server.close(r));});
  await check('batch sample uses five actual source images and content items rather than page text boxes',async()=>{
    await admin.goto(base+'/admin/#/textbooks');await btn('导入教材').click();await btn('载入真实教材书页').click();
    await expect(admin.locator('.upload-files tbody tr')).toHaveCount(5);await btn('上传并开始整理').click();await expect(admin.locator('.material-organizer')).toBeVisible();
    await expect(admin.locator('.material-tree-item')).toHaveCount(9);await expect(admin.locator('.source-paper img')).toHaveAttribute('src','/admin/materials/bnu6a/page-49.png');
    assert.equal(await admin.locator('.source-paper img').evaluate(i=>i.complete&&i.naturalWidth===1087),true);
    for(const page of [49,50,91,92,93]){const r=await admin.request.get(base+'/admin/materials/bnu6a/page-'+page+'.png');assert.equal(r.status(),200);assert.ok((await r.body()).length>500000);}
    await btn('确认本课整理结果').click();await expect(admin.getByRole('alert')).toContainText('合并');
    await admin.screenshot({path:output+'/01-organizer.png',fullPage:true});
  });
  await check('cross-page merge retains both methods; question preview hides teaching scaffolds',async()=>{
    await btn('合并内容').click();await admin.getByLabel('要并入的内容').selectOption('MAT-METHODS');await btn('确认合并').click();
    await expect(admin.locator('.material-tree-item')).toHaveCount(8);await expect(admin.locator('[data-block="B-METHOD-A"]')).toBeVisible();
    await admin.getByRole('tab',{name:'仅题目与条件',exact:true}).click();await expect(admin.locator('[data-block="B-DRAW-Q"]')).toBeVisible();await expect(admin.locator('[data-block="B-SOLVE-Q"]')).toBeVisible();await expect(admin.locator('[data-block="B-ANSWER-BLANK"]')).toBeVisible();await expect(admin.locator('[data-block="B-METHOD-A"]')).toHaveCount(0);await expect(admin.locator('[data-block="B-HINT"]')).toHaveCount(0);
    await admin.getByRole('tab',{name:'完整讲解材料',exact:true}).click();await btn('原页 50 ↗').first().click();await expect(admin.locator('.source-paper img')).toHaveAttribute('src',/page-50/);await expect(admin.locator('.source-region.selected')).toHaveCount(1);
    await btn('放大原页').click();await expect(admin.getByRole('dialog').locator('img')).toHaveAttribute('src',/page-50/);await admin.getByRole('button',{name:'关闭对话框',exact:true}).click();
    await edit('B-QUESTION');await admin.getByLabel('整理文字').fill('取消的修改');await btn('取消').click();await expect(admin.locator('[data-block="B-QUESTION"]')).not.toContainText('取消的修改');
    await admin.screenshot({path:output+'/02-cross-page.png',fullPage:true});
    await admin.locator('[data-block="B-DIAGRAM"]').screenshot({path:output+'/02-diagrams.png'});
  });
  await check('split and regroup preserve source regions; deliberately incorrect examples remain uncorrected',async()=>{
    await btn('调整结构').click();await admin.getByRole('dialog').getByRole('checkbox',{name:/教材中的引导问题/}).check();await admin.getByLabel('新内容名称').fill('单独查看的思考提示');await btn('保存结构调整').click();
    await expect(admin.locator('.material-tree-item')).toHaveCount(9);await btn('合并内容').click();await admin.getByLabel('要并入的内容').selectOption(await admin.getByRole('option',{name:/单独查看的思考提示/}).getAttribute('value'));await btn('确认合并').click();await expect(admin.locator('.material-tree-item')).toHaveCount(8);
    await tree('判断并解释计算错误').click();await admin.getByRole('tab',{name:'仅题目与条件',exact:true}).click();await expect(admin.locator('[data-block="B-ERROR-WORK"] svg image')).toHaveAttribute('href',/page-50/);await expect(admin.locator('[data-block="B-ERROR-HINT"]')).toHaveCount(0);
    await btn('确认本课整理结果').click();await expect(admin.getByRole('status')).toContainText('本课内容已核对');
  });
  await check('blank tables remain blank and data-table correction preserves headers, units and references',async()=>{
    await tree('设计研究方案').click();await expect(admin.locator('[data-block="B-PLAN-BLANK"] svg')).toBeVisible();
    await tree('整理与比较人口数据').click();await edit('B-COUNTS');await expect(admin.getByLabel('表头 3',{exact:true})).toHaveValue('65岁以下人数');await admin.getByLabel('表头 3',{exact:true}).fill('65岁及以上人数');await admin.getByRole('dialog').getByRole('checkbox').check();await btn('保存内容').click();
    await expect(admin.locator('[data-block="B-COUNTS"] table')).toContainText('65岁及以上人数');await expect(admin.locator('[data-block="B-COUNTS"] table')).toContainText('129977870');
    await btn('确认本课整理结果').click();await expect(admin.getByRole('status')).toContainText('本课内容已核对');
    await admin.screenshot({path:output+'/03-table.png',fullPage:true});
  });
  await check('charts keep legends and cross-page data links, and all organization survives reload',async()=>{
    await tree('同一组数据的三种统计图').click();await edit('B-PIE');await admin.getByLabel('关联内容',{exact:true}).selectOption(['B-AGE']);await admin.getByRole('dialog').getByRole('checkbox').check();await btn('保存内容').click();await btn('确认本课整理结果').click();
    await admin.locator('[data-block="B-PIE"] .block-references button').click();await expect(admin.locator('.organized-panel h3')).toHaveText('整理与比较人口数据');await expect(admin.locator('.source-paper img')).toHaveAttribute('src',/page-91/);
    await tree('同一组数据的三种统计图').click();await admin.locator('[data-block="B-PIE"]').screenshot({path:output+'/04-pie.png'});assert.ok(await admin.locator('[data-block="B-PIE"] svg').evaluate(s=>{const r=s.getBoundingClientRect(),v=s.viewBox.baseVal;return Math.abs(r.width/r.height-v.width/v.height)<0.01;}));await admin.screenshot({path:output+'/04-charts.png',fullPage:true});
    await admin.reload();await expect(admin.locator('.organized-panel h3')).toHaveText('同一组数据的三种统计图');await expect(admin.locator('.organizer-heading')).toContainText('3 个课题已核对');
    await admin.setViewportSize({width:1024,height:768});assert.ok(await admin.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.ok(await admin.locator('.page-container').evaluate(e=>e.scrollWidth<=e.clientWidth));await admin.screenshot({path:output+'/05-narrow.png',fullPage:true});await admin.setViewportSize({width:1600,height:1050});
  });
  await check('correct Task and recursive solutions are adopted; the student receives real organized material',async()=>{
    await btn('下一步：关联模型').click();await btn('采用此关联建议').click();await expect(admin.locator('.mapping-table')).toContainText('连续求一个量的几分之几');await expect(admin.locator('.knowledge-table tbody tr')).toHaveCount(3);
    await btn('下一步：目标与应用').click();await btn('生成目标建议').click();await expect(admin.locator('.import-requirements tbody tr')).toHaveCount(4);await btn('应用并供学生选用').click();await expect(admin.locator('.import-success')).toBeInViewport();
    await student.goto(base+'/student/');await student.locator('.space-trigger').click();await student.getByRole('button',{name:'＋ 新建学习空间',exact:true}).click();await student.getByRole('button',{name:'创建学习空间',exact:true}).click();
    await student.locator('.chapter-row').filter({hasText:'分数的应用（一）'}).getByRole('button',{name:'查看本课材料',exact:true}).click();await expect(student.locator('.material-reader [data-block="B-METHOD-A"]')).toBeVisible();
    await student.getByRole('button',{name:'只看题目',exact:true}).click();await expect(student.locator('.material-reader [data-block="B-METHOD-A"]')).toHaveCount(0);await expect(student.locator('.material-reader [data-block="B-CONDITIONS"] svg image')).toHaveAttribute('href',/page-49/);
    await student.screenshot({path:output+'/06-student.png',fullPage:true});
    await student.getByRole('button',{name:/第九单元 数据的表示和分析/}).click();await student.locator('.chapter-row').filter({hasText:'建设适老社会（二）'}).getByRole('button',{name:'查看本课材料',exact:true}).click();
    await student.locator('.material-reader [data-block="B-PIE"]').getByRole('button',{name:'三次人口普查的年龄段占比 ↗',exact:true}).click();await expect(student.locator('.reader-reference table')).toContainText('17.95');await expect(student.locator('.reader-reference')).toContainText('91页');
    await student.locator('.reader-reference').screenshot({path:output+'/07-student-reference.png'});
    assert.equal(modelCalls,0);assert.deepEqual(posts,[]);assert.deepEqual(errors,[]);const data=await state();assert.ok(data.books[0].units[0].chapters[0].items.some(i=>i.blocks.some(b=>b.id==='B-METHOD-B')));
  });
});
