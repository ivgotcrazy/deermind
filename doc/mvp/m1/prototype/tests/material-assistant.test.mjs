import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir,writeFile } from 'node:fs/promises';
import { chromium,expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';
const expect=baseExpect.configure({timeout:8000});
const output=new URL('../test-results/material-assistant/',import.meta.url);

test('textbook assistant keeps scoped conversations and explicit candidate adoption',async t=>{
  await mkdir(output,{recursive:true});const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'msedge'});const page=await browser.newPage({viewport:{width:1500,height:1000}});page.setDefaultTimeout(8000);
  const errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/api/**',r=>{calls.push(r.request().url());return r.abort();});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=name=>page.getByRole('button',{name,exact:true});
  const data=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-import-v1'))[0]);
  const domain=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')));
  const send=async text=>{await page.getByLabel('给教材助手的消息').fill(text);await btn('发送').click();};
  const lastCard=()=>page.locator('.candidate-card').last();
  const shot=async name=>page.screenshot({path:new URL(name+'.png',output).pathname.replace(/^\/([A-Z]:)/,'$1'),fullPage:true});
  const gotoChapter=async chapter=>{const d=await data();await page.evaluate(hash=>location.hash=hash,'/textbooks?'+new URLSearchParams({source:d.id,chapter,view:'content'}));};
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/textbooks');await btn('导入教材').click();await expect(btn('上传并开始整理')).toBeDisabled();await btn('载入四例核对样例').click();await btn('上传并开始整理').click();
  await expect(page.locator('.material-assistant')).toBeVisible();const initial=await data(),model=await domain();
  await t.test('no reference asks for clarification; chapter browsing never retargets the conversation',async()=>{
    await send('请修正这道题');await expect(page.locator('.assistant-message').last()).toContainText('请先');await expect(page.locator('.candidate-card')).toHaveCount(0);
    await btn('请助手修正 跨页题目与两种原有解法').click();await gotoChapter('统计图');await expect(page.locator('.composer-reference')).toContainText('跨页题目与两种原有解法');await gotoChapter('分数的应用');
    await send('核对完整题目，不加入解法');await expect(page.locator('.candidate-preview')).toContainText('三个兴趣小组的人数');assert.deepEqual((await data()).flow.elements,initial.flow.elements);
    await btn('修改前').click();await expect(page.locator('.candidate-preview')).toContainText('跨页题目与两种原有解法');await btn('修正后').click();
    await btn('查看原页').click();await page.locator('.candidate-preview img').evaluate(img=>img.decode());await shot('01-candidate-source');
    await lastCard().getByRole('button',{name:'不采用',exact:true}).click();assert.deepEqual((await data()).flow.elements,initial.flow.elements);await btn('返回内容列表').click();
  });
  await t.test('two rounds of solution correction preserve the single parent and survive reload',async()=>{
    await btn('教材解法 1').click();await btn('请助手修正 教材解法 1').click();await send('这里是两种解法，请分开');await expect(page.locator('.candidate-preview .parsed-element-view')).toHaveCount(2);
    await lastCard().getByRole('button',{name:'继续修正',exact:true}).click();await send('再核对两个解法的公式和单位');await expect(page.locator('.candidate-card').nth(1)).toContainText('已由后续候选替代');
    await expect(page.locator('.candidate-preview .parsed-element-view')).toHaveCount(2);assert.deepEqual((await data()).flow.elements,initial.flow.elements);
    await page.getByLabel('给教材助手的消息').fill('这段还需要继续检查');const before=await data();await page.reload();await expect(page.getByLabel('给教材助手的消息')).toHaveValue('这段还需要继续检查');assert.deepEqual((await data()).flow.assistant,before.flow.assistant);
    await lastCard().getByRole('button',{name:'查看结果',exact:true}).click();await shot('02-continuous-correction');await lastCard().getByRole('button',{name:'采用结果',exact:true}).click();
    const after=await data(),solutions=after.flow.elements.filter(e=>e.kind==='solution');assert.equal(solutions.length,2);assert.ok(solutions.every(e=>e.taskElementId==='C02-question'));assert.deepEqual(after.flow.elements.filter(e=>e.kind!=='solution'),initial.flow.elements.filter(e=>e.kind!=='solution'));assert.deepEqual(await domain(),model);assert.deepEqual(after.flow.links,{});
    await expect(lastCard().getByRole('button',{name:'采用结果',exact:true})).toHaveCount(0);await btn('返回内容列表').click();
  });
  await t.test('chart correction supports retry and renders structured charts before adopting',async()=>{
    await gotoChapter('统计图');await btn('请助手修正 三种统计图与教学提示').click();const before=(await data()).flow.elements;
    await send('模拟处理失败');await expect(page.locator('.assistant-message').last()).toContainText('读取失败');assert.deepEqual((await data()).flow.elements,before);
    await btn('重试').click();await expect(page.locator('.candidate-preview svg')).toHaveCount(3);await send('请再核对三张图的数据和单位');await expect(page.locator('.candidate-preview svg')).toHaveCount(3);await shot('03-charts');
    await lastCard().getByRole('button',{name:'采用结果',exact:true}).click();await btn('返回内容列表').click();await expect(page.getByLabel('选择 三种统计图与教学提示')).toBeEnabled();assert.deepEqual(await domain(),model);
  });
  await t.test('missing appendix requests material; unrelated prompts do not pretend to extract',async()=>{
    await gotoChapter('圆');await btn('请助手修正 六种平面图形和原图标记').click();const before=await data();await send('请核对图形及附页');await expect(page.locator('.assistant-message').last()).toContainText('附页没有提供');assert.deepEqual((await data()).flow.elements,before.flow.elements);await shot('04-missing-material');
    await page.getByLabel('补充材料',{exact:true}).setInputFiles({name:'appendix.png',mimeType:'image/png',buffer:Buffer.from([1,2,3])});await expect(page.locator('.assistant-message').last()).toContainText('未上传或识别');assert.deepEqual((await data()).flow.elements,before.flow.elements);
    await gotoChapter('分数的应用');await btn('请助手修正 跨页题目与两种原有解法').click();await send('帮我写一篇作文');await expect(page.locator('.assistant-message').last()).toContainText('尚未接入真实Agent');
    await btn('收起助手').click();await page.reload();await expect(page.locator('.material-assistant')).toHaveCount(0);await btn('展开教材助手').click();await expect(page.locator('.assistant-message').last()).toContainText('尚未接入真实Agent');
  });
  await t.test('old draft contents and later unrelated changes are preserved',async()=>{
    await send('核对题目');const stored=await data();await page.evaluate(()=>{const d=JSON.parse(localStorage.getItem('deermind-m1-import-v1'));d[0].flow.elements.find(e=>e.id==='C02-question').sourceNote+='后续修订';localStorage.setItem('deermind-m1-import-v1',JSON.stringify(d));});await page.reload();
    await lastCard().getByRole('button',{name:'采用结果',exact:true}).click();await expect(page.locator('.material-assistant [role=alert]')).toContainText('源内容已经变化');assert.equal((await data()).flow.elements.find(e=>e.id==='C02-question').sourceNote,stored.flow.elements.find(e=>e.id==='C02-question').sourceNote+'后续修订');
    await page.setViewportSize({width:1280,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot('05-workspace-1280');
    await page.setViewportSize({width:760,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  });
  assert.deepEqual(errors,[]);assert.deepEqual(calls,[]);await writeFile(new URL('review.json',output),JSON.stringify({status:'passed',modelCalls:0,errors,cases:['clarify','explicit-reference','candidate-preview','discard','continuous-correction','reload','adopt','retry','charts','missing-source','stale-candidate','responsive']},null,2));
});
