import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir,writeFile } from 'node:fs/promises';
import { chromium,expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';
const expect=baseExpect.configure({timeout:10000});
const output=new URL('../test-results/content-review/',import.meta.url);
test('four source-review workflows preserve content, ownership and matching boundaries',async t=>{
  await mkdir(output,{recursive:true});const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1500,height:1050}});const page=await context.newPage();
  page.setDefaultTimeout(10000);const errors=[],network=[];page.on('pageerror',e=>errors.push(e.message));await context.route('**/api/**',r=>{network.push(r.request().url());return r.abort();});
  page.on('dialog',d=>d.accept());
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=name=>page.getByRole('button',{name,exact:true});const modal=()=>page.getByRole('dialog');
  const data=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-import-v1'))[0]);
  const current=async key=>(await data()).contentReview.items.find(i=>i.id===key);
  const select=async key=>{await page.locator('.review-item').filter({hasText:({C02:'跨页题目',C03:'错误演算',C05:'三种统计图',C06:'六种平面'})[key]}).click();await btn('内容核对').click();};
  const shot=async name=>{if(!await modal().count())await page.locator('.page-container').evaluate(el=>el.scrollTop=0);await page.screenshot({path:new URL(name+'.png',output).pathname.replace(/^\/([A-Z]:)/,'$1'),fullPage:true});};
  const confirm=async()=>{await page.getByLabel('已对照原页核对完整内容、用途与重绘结果').check();await btn('核对完成，进入模型匹配').click();await expect(page.locator('.match-table')).toBeVisible();};
  const selectMatches=async()=>{for(const row of await page.locator('.match-table tbody tr').all()){await row.getByRole('button').click();await modal().getByRole('button',{name:'确认选用',exact:true}).click();}};
  const addChart=async title=>{
    await page.locator('.review-part[data-role="question"]').getByRole('button',{name:'添加内容',exact:true}).click();await modal().getByLabel('内容形式').selectOption('chart');await modal().getByRole('button',{name:'填写内容',exact:true}).click();
    await modal().getByText('从所选区域重新提取',{exact:true}).click();await modal().getByRole('button',{name:'查看提取候选',exact:true}).click();await modal().getByLabel('候选内容').selectOption({label:title});await modal().getByRole('button',{name:'采用候选到编辑区',exact:true}).click();
  };
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/textbooks');
  await btn('导入教材').click();await btn('载入四例核对样例').click();await btn('上传并开始整理').click();await expect(page.locator('.content-review-workspace')).toBeVisible();
  assert.equal((await data()).contentReview.items.length,4);
  await t.test('C05 missing charts can be added, copied and validated without altering raw extraction',async()=>{
    await select('C05');assert.equal((await current('C05')).original.flatMap(p=>p.blocks).filter(b=>b.type==='chart').length,0);
    await addChart('第五～七次人口普查中老年人口数量统计图');
    await modal().getByLabel('数值 1 1',{exact:true}).fill('-2');await modal().getByRole('button',{name:'保存修改',exact:true}).click();await expect(modal().getByRole('alert')).toContainText('数值');await modal().getByLabel('数值 1 1',{exact:true}).fill('1.30');await shot('C05-edit-chart');await modal().getByRole('button',{name:'保存修改',exact:true}).click();
    await page.locator('[data-block="chart"]').getByRole('button',{name:'复制图表',exact:true}).click();await modal().getByLabel('图类型',{exact:true}).selectOption('line');await modal().getByLabel('图名',{exact:true}).fill('第五～七次人口普查中老年人口数量变化情况');await modal().getByRole('button',{name:'保存修改',exact:true}).click();
    await addChart('第七次人口普查年龄分布图');await modal().getByLabel('数值 1 1',{exact:true}).fill('20');await modal().getByRole('button',{name:'保存修改',exact:true}).click();await expect(modal().getByRole('alert')).toContainText('100%');await modal().getByLabel('数值 1 1',{exact:true}).fill('17.95');await modal().getByRole('button',{name:'保存修改',exact:true}).click();
    await expect(page.locator('[data-block="chart"]')).toHaveCount(3);await btn('预览学生题面').click();await expect(modal().getByTestId('review-student-preview').locator('svg')).toHaveCount(3);await expect(modal().getByTestId('review-student-preview')).not.toContainText('条形统计图很容易');await btn('关闭对话框').click();
    await confirm();await selectMatches();await btn('保存模型关联').click();await expect(page.getByRole('status')).toContainText('模型关联已保存');await shot('C05-matched');assert.equal((await current('C05')).original.flatMap(p=>p.blocks).filter(b=>b.type==='chart').length,0);
  });
  await t.test('C03 syntax correction preserves deliberately incorrect mathematics and missing source solution',async()=>{
    await select('C03');await page.locator('[data-block="formula"]').getByRole('button',{name:'编辑',exact:true}).click();
    await modal().getByLabel('算式 1',{exact:true}).fill('7/8 × 3/4 ÷ (');await modal().getByRole('button',{name:'保存修改',exact:true}).click();await expect(modal().getByRole('alert')).toContainText('无法解析');
    await modal().getByLabel('算式 1',{exact:true}).fill('7/8 × 3/4 ÷ 1/3');await modal().getByLabel('算式 2',{exact:true}).fill('= 7/8 × 3/4 × 1/3');await modal().getByLabel('算式 3',{exact:true}).fill('= 7/32');await modal().getByRole('button',{name:'保存修改',exact:true}).click();await shot('C03-content');
    await confirm();await selectMatches();await btn('保存模型关联').click();const item=await current('C03');assert.equal(item.parts.filter(p=>p.role==='solution').length,0);assert.equal(item.parts.flatMap(p=>p.blocks).find(b=>b.type==='formula').lines[2],'= 7/32');
  });
  await t.test('C06 geometry, per-item invalidation, persistence and domain isolation',async()=>{
    await select('C06');const square=page.locator('[data-block="shapes"] svg rect');assert.equal(await square.getAttribute('width'),await square.getAttribute('height'));await expect(page.locator('[data-block="shapes"] svg circle[fill="#c62a7c"]')).toHaveCount(6);await shot('C06-content');await confirm();await selectMatches();await btn('保存模型关联').click();await page.reload();await expect(page.locator('.match-table')).toBeVisible();
    await btn('内容核对').click();await page.locator('[data-block="shapes"]').getByRole('button',{name:'编辑',exact:true}).click();await modal().getByLabel('可见标记点').first().selectOption('none');await modal().getByRole('button',{name:'保存修改',exact:true}).click();await btn('模型关联').click();await expect(btn('保存模型关联')).toBeDisabled();assert.ok((await current('C05')).matched);assert.equal((await current('C06')).matched,'');
    await btn('内容核对').click();await page.locator('[data-block="shapes"]').getByRole('button',{name:'编辑',exact:true}).click();await modal().getByLabel('可见标记点').first().selectOption('center_like');await modal().getByRole('button',{name:'保存修改',exact:true}).click();await confirm();await btn('保存模型关联').click();
  });
  await t.test('C02 separates two source solutions, moves blank/prompt and binds each method',async()=>{
    await select('C02');let solution=page.locator('.review-part[data-role="solution"]').first();
    await solution.locator('[data-block="formula"]').first().getByRole('button',{name:'编辑',exact:true}).click();await modal().getByLabel('算式 1',{exact:true}).fill('12 × 1/3 × 3/4');await modal().getByLabel('算式 2',{exact:true}).fill('= 3');await modal().getByRole('button',{name:'删除算式 3',exact:true}).click();await modal().getByLabel('结果单位',{exact:true}).fill('人');await modal().getByLabel('仍有内容待补').uncheck();await modal().getByRole('button',{name:'保存修改',exact:true}).click();
    // Select the second method's text and equation by the actual displayed block order.
    let part=(await current('C02')).parts.find(p=>p.role==='solution');const second=part.blocks.findIndex(b=>b.text.includes('先求航模'));
    await solution.getByRole('button',{name:'拆分解法',exact:true}).click();await modal().getByLabel('新解法名称').fill('先合并两层比例');await modal().locator('.split-choice input').nth(second).check();await modal().locator('.split-choice input').nth(second+1).check();await modal().getByRole('button',{name:'移到新解法',exact:true}).click();await expect(page.locator('.review-part[data-role="solution"]')).toHaveCount(2);
    const secondSolution=page.locator('.review-part[data-role="solution"]').nth(1);
    await secondSolution.locator('[data-block="formula"]').getByRole('button',{name:'编辑',exact:true}).click();await modal().getByLabel('算式 1',{exact:true}).fill('12 × (1/3 × 3/4)');await modal().getByLabel('算式 2',{exact:true}).fill('= 12 × 1/4');await modal().getByLabel('算式 3',{exact:true}).fill('= 3');await modal().getByLabel('结果单位',{exact:true}).fill('人');await modal().getByLabel('仍有内容待补').uncheck();await modal().getByRole('button',{name:'保存修改',exact:true}).click();
    // Source question and answer blank were mistakenly placed inside the first solution.
    for(const phrase of ['请列式解决问题','答']){
      const block=page.locator('.review-part[data-role="solution"] .review-content').filter({hasText:phrase});
      if(await block.count()){await block.first().getByRole('button',{name:'移动到…',exact:true}).click();await modal().getByLabel('所属内容').selectOption({label:'题面'});await modal().getByRole('button',{name:'确认移动',exact:true}).click();}
    }
    const hint=page.locator('.review-part[data-role="solution"] .review-content').filter({hasText:'你能看懂笑笑的方法吗'});await hint.getByRole('button',{name:'移动到…',exact:true}).click();await modal().getByLabel('所属内容').selectOption('new');await modal().getByRole('button',{name:'确认移动',exact:true}).click();
    const answer=page.locator('.review-part[data-role="question"] .review-content').filter({has:page.getByText('答：',{exact:true})});await answer.getByRole('button',{name:'编辑',exact:true}).click();await modal().getByLabel('文字内容').fill('答：________________。');await modal().getByRole('button',{name:'保存修改',exact:true}).click();
    await btn('预览学生题面').click();await expect(modal().getByTestId('review-student-preview')).not.toContainText('你能看懂笑笑');await expect(modal().getByTestId('review-student-preview')).not.toContainText('先求摄影');await btn('关闭对话框').click();
    await shot('C02-split');await confirm();await selectMatches();await page.getByLabel('A · 气象人数',{exact:true}).fill('12');await page.getByLabel('r · 摄影相对气象的比例',{exact:true}).fill('1/3');await page.getByLabel('s · 航模相对摄影的比例',{exact:true}).fill('3/4');await btn('保存模型关联').click();await expect(page.getByRole('status')).toContainText('模型关联已保存');await shot('C02-matched');
    const item=await current('C02');assert.equal(item.parts.filter(p=>p.role==='solution').length,2);assert.equal(new Set(item.parts.filter(p=>p.role==='solution').map(p=>p.templateId)).size,2);
    const instances=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')).instances);const q=instances.find(q=>q.id===item.instanceId);assert.equal(q.solutions.length,2);assert.ok(q.solutions.every(s=>s.taskInstanceId===q.id));assert.equal(q.checkedSignature,'');assert.ok(q.reviewContent);
  });
  await t.test('saved domain instance retains charts and returns to the exact review item',async()=>{
    const d=await data(),c=await current('C05'),task=c.parts.find(p=>p.role==='question').templateId;
    await page.evaluate(hash=>location.hash=hash,'/domain?domain='+d.book.domainId+'&kind=task&id='+task+'&tab=instances');await page.locator('.question-cell .text-link').click();await expect(modal().locator('svg')).toHaveCount(3);await modal().getByRole('button',{name:'预览学生题面',exact:true}).click();await expect(modal().locator('svg')).toHaveCount(3);await modal().getByRole('link',{name:'返回教材核对处修改',exact:true}).click();await expect(page.locator('.review-result h3')).toHaveText('三种统计图与教学提示');await expect(page.locator('[data-block="chart"]')).toHaveCount(3);
  });
  await page.setViewportSize({width:1280,height:900});await btn('内容核对').click();assert.ok(await page.locator('.page-container').evaluate(el=>el.scrollWidth<=el.clientWidth));await page.reload();await expect(page.locator('.review-result')).toBeVisible();assert.equal((await data()).contentReview.items.filter(i=>!!i.matched).length,4);assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
  await writeFile(new URL('review.json',output),JSON.stringify({status:'passed',cases:['C02','C03','C05','C06'],errors,modelCalls:network.length,scope:'Mock interaction and ownership checks; not model quality or course readiness'},null,2));
});
