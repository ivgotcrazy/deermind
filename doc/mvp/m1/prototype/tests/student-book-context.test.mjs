import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium, expect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

test('教材浏览与活动独立，只有明确书页请求才附带引用',async t=>{
  const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch();t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage(),errors=[],api=[];
  page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/api/**',r=>{api.push(r.request().url());return r.abort();});
  const b=name=>page.getByRole('button',{name,exact:true});
  const prompt=page.locator('#student-prompt');
  const heading=page.getByLabel('当前活动',{exact:true});
  const last=page.getByRole('log').locator('article').last();
  const saved=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-student-trial-space-v1')));
  const say=async text=>{await prompt.fill(text);await b('发送').click();};
  await page.goto('http://127.0.0.1:'+server.address().port+'/student/?mode=records');
  await page.getByLabel('教材',{exact:true}).selectOption('BNU-6A');
  await page.getByLabel('学习目标').selectOption({index:1});await b('创建并进入教材').click();

  await t.test('任何章节均可开始聊天，不附带浏览位置',async()=>{
    await page.getByLabel('章节').selectOption('建设适老社会（一）');
    await expect(prompt).toBeVisible();await expect(b('回到可讲解章节')).toHaveCount(0);
    await say('讲讲增加四分之一');
    await expect(heading).toContainText('增加四分之一');
    await expect(last).toContainText('100 本');
    await expect(page.locator('.book-reference')).toHaveCount(0);
    assert.equal((await saved()).turns.at(-1).bookReference,undefined);
    await expect(page.getByLabel('章节')).toHaveValue('建设适老社会（一）');
  });
  await t.test('切章、翻页、刷新保留活动与草稿，原活动操作仍可用',async()=>{
    const before=await saved();await prompt.fill('草稿：我还有一个问题');
    await page.getByLabel('章节').selectOption('分数的应用（一）');await b('下一页').click();
    await page.reload();
    const after=await saved();assert.equal(after.activeId,before.activeId);assert.deepEqual(after.activities,before.activities);assert.deepEqual(after.turns,before.turns);assert.deepEqual(after.notices,before.notices);
    await expect(prompt).toHaveValue('草稿：我还有一个问题');
    await page.getByLabel('章节').selectOption('建设适老社会（一）');
    await b('没懂，画给我看').click();await expect(last).toContainText('每格 20 本');
    await expect(last.locator('.book-reference')).toHaveCount(0);
    assert.equal((await saved()).activeId,before.activeId);
  });
  await t.test('明确引用当前页覆盖旧示例，不误套四分之一；出处不会随翻页变动',async()=>{
    const source=(await saved()).page;
    await say('这页没看懂，请讲讲这一页');
    await expect(last.locator('.book-reference')).toContainText('建设适老社会（一）');
    await expect(last.locator('.book-reference')).toContainText('第 '+source+' 页');
    await expect(last.locator('figure')).toHaveCount(0);
    const reference=(await saved()).turns.at(-1).bookReference;
    await page.getByLabel('章节').selectOption('分数的应用（一）');await b('下一页').click();
    assert.deepEqual((await saved()).turns.at(-1).bookReference,reference);
    await expect(last.locator('.book-reference')).toContainText('建设适老社会（一）');
    await say('讲讲这一页');await expect(last.locator('.book-reference')).toContainText('第 50 页');
    await expect(last).toContainText('先合并两层比例');
  });
  await t.test('收起教材仍可提问，不偷偷引用隐藏书页',async()=>{
    await b('收起教材').click();
    await say('讲讲增加四分之一');await expect(last).toContainText('100 本');
    await expect(last.locator('.book-reference')).toHaveCount(0);
    await say('讲讲这一页');await expect(last).toContainText('你指教材的哪一页');
    await expect(last.locator('.book-reference')).toHaveCount(0);
    await expect(b('展开教材')).toBeVisible();
    await say('换个内容，讲讲统计图');
    await expect(heading).toContainText('统计图');await expect(heading).not.toContainText('增加四分之一');
    await expect(last).toContainText('当前 mock 尚未预写');await expect(last).not.toContainText('看第 50 页');
    await expect(prompt).toBeVisible();
  });
  await t.test('浏览其他章不关闭检测答题区或取消活动',async()=>{
    await b('结束当前活动').click();await say('讲讲增加四分之一');
    await b('我想测一下').click();await b('开始检测').click();
    await page.getByLabel('我的答案（本）').fill('150');
    const before=await saved();await b('展开教材').click();
    await page.getByLabel('章节').selectOption('建设适老社会（一）');
    await expect(page.getByLabel('我的答案（本）')).toHaveValue('150');
    await expect(heading).toContainText('独立作答中');
    assert.equal((await saved()).activeId,before.activeId);
    await b('提交作答').click();await expect(heading).toContainText('本轮已结束');
    await b('结束本次检测').click();await expect(prompt).toBeVisible();
    await mkdir('test-results/student-book-context',{recursive:true});
    await page.screenshot({path:'test-results/student-book-context/other-chapter-current-activity.png'});
  });
  assert.deepEqual(errors,[]);assert.deepEqual(api,[]);
});
