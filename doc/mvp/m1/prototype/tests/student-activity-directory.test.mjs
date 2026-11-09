import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium, expect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

test('活动目录：森林、定位、回看、收起与恢复',async t=>{
  const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch();t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const context=await browser.newContext({viewport:{width:1600,height:1000}});
  const page=await context.newPage(),errors=[],api=[];
  page.on('pageerror',e=>errors.push(e.message));await context.route('**/api/**',r=>{api.push(r.request().url());return r.abort();});
  const key='deermind-m1-student-trial-space-v1';
  const b=name=>page.getByRole('button',{name,exact:true});
  const saved=()=>page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key);
  const say=async text=>{await page.locator('#student-prompt').fill(text);await b('发送').click();};
  const directory=page.getByLabel('活动目录',{exact:true}),heading=page.getByLabel('当前活动',{exact:true});
  const locate=id=>directory.locator(`button[data-activity="${id}"]`);
  await mkdir('test-results/student-activity-directory',{recursive:true});
  const shot=name=>page.screenshot({path:`test-results/student-activity-directory/${name}.png`});
  await page.goto('http://127.0.0.1:'+server.address().port+'/student/?mode=records');
  await page.getByLabel('教材',{exact:true}).selectOption('BNU-6A');await page.getByLabel('学习目标').selectOption({index:1});await b('创建并进入教材').click();
  await expect(directory).toContainText('活动会自动出现在这里');
  await b('讲讲增加四分之一').click();const root=(await saved()).activeId;
  await b('先问一个相关问题').click();const child=(await saved()).activeId;
  await expect(locate(child)).toContainText('当前');
  await b('回到原来的主线').click();await say('我想检测');await b('开始检测').click();
  const assessment=(await saved()).activeId;
  await b('结束检测并求助').click();await b('讲讲刚才这道题').click();const nested=(await saved()).activeId;

  await t.test('开始时间、名称、嵌套关系；箭头不定位、不改变活动',async()=>{
    await expect(locate(nested)).toContainText('120本增加四分之一的解法');
    for(const a of (await saved()).activities)assert.ok(Number.isFinite(Date.parse(a.startedAt)));
    const before=await saved(),position=await page.locator('.transcript').evaluate(el=>el.scrollTop);
    await directory.getByRole('button',{name:'收起子活动：增加四分之一检测',exact:true}).click();
    await expect(locate(nested)).toHaveCount(0);
    await directory.getByRole('button',{name:'展开子活动：增加四分之一检测',exact:true}).click();
    await expect(locate(nested)).toBeVisible();assert.equal((await saved()).activeId,before.activeId);
    assert.deepEqual((await saved()).activities,before.activities);
    assert.equal(await page.locator('.transcript').evaluate(el=>el.scrollTop),position);
    await shot('01-current-nested');
  });
  await b('回到原来的主线').click();await b('结束本次检测').click();await b('结束当前活动').click();
  await say('换个话题，聊聊天');const current=(await saved()).activeId;
  await page.locator('#student-prompt').fill('尚未发送的草稿');

  await t.test('定位根活动与子活动，只滚动聊天，当前活动及草稿不变',async()=>{
    const before=await saved();
    await locate(root).click();await expect(page.locator('.review-banner')).toContainText('正在回看：增加四分之一');
    const target=page.locator(`[data-activity-start="${root}"]`);
    await expect(target).toHaveClass(/activity-highlight/);
    const delta=await target.evaluate(el=>el.getBoundingClientRect().top-el.closest('.transcript').getBoundingClientRect().top);
    assert.ok(delta>=0&&delta<20);
    assert.equal((await saved()).activeId,current);assert.deepEqual((await saved()).activities,before.activities);
    await expect(heading.locator('[aria-current]')).toHaveText('自由交谈');
    await expect(locate(current)).toHaveAttribute('aria-current','true');
    await locate(child).click();await expect(page.locator('.review-banner')).toContainText('分母为什么不能为零');
    await expect(page.locator('#student-prompt')).toHaveValue('尚未发送的草稿');
    assert.equal((await saved()).page,before.page);assert.equal((await saved()).chapter,before.chapter);
    await shot('02-history-lookup');
  });
  await t.test('收起、展开、刷新保留历史位置；回到当前活动不恢复旧轮',async()=>{
    await b('收起活动目录').click();await expect(directory).toHaveCount(0);
    await expect(page.locator('.review-banner')).toContainText('分母为什么不能为零');
    await b('展开活动目录').click();await expect(directory).toBeVisible();
    const top=await page.locator('.transcript').evaluate(el=>el.scrollTop);await page.reload();
    await expect(page.locator('.review-banner')).toContainText('分母为什么不能为零');
    await expect.poll(()=>page.locator('.transcript').evaluate(el=>el.scrollTop)).toBeCloseTo(top,0);
    await locate(assessment).click();await expect(b('提交作答')).toHaveCount(0);
    await b('回到当前活动').click();await expect(page.locator('.review-banner')).toHaveCount(0);
    assert.equal((await saved()).activeId,current);assert.equal((await saved()).turns.filter(t=>t.check).length,1);
    await b('收起对话').click();await locate(child).click();
    await expect(page.getByRole('log')).toBeVisible();await expect(page.getByRole('img')).toBeVisible();
    assert.equal((await saved()).activeId,current);
  });
  await t.test('回看时追加提示不抢滚动位置，发送仍属于当前活动',async()=>{
    const top=await page.locator('.transcript').evaluate(el=>el.scrollTop);
    // Trigger a current-activity update without Playwright scrolling its button into view.
    await b('暂停学习').evaluate(el=>el.click());
    await expect(heading).toContainText('已暂停');
    assert.equal(await page.locator('.transcript').evaluate(el=>el.scrollTop),top);
    await b('回到当前活动').click();await b('继续刚才的学习').first().click();
    await locate(child).click();await say('今天想轻松聊聊');
    await expect(page.locator('.review-banner')).toHaveCount(0);
    assert.equal((await saved()).turns.at(-1).activityId,current);
  });
  await t.test('窄屏以侧栏展示，定位后关闭；Escape和遮罩均可收起',async()=>{
    await page.setViewportSize({width:390,height:844});await expect(directory).toHaveCount(0);
    await b('展开活动目录').click();await expect(directory).toHaveClass(/directory-overlay/);await shot('03-mobile-directory');
    await locate(child).click();await expect(directory).toHaveCount(0);
    await expect(page.locator('.review-banner')).toContainText('分母为什么不能为零');
    await b('展开活动目录').click();await page.keyboard.press('Escape');await expect(directory).toHaveCount(0);
    await b('展开活动目录').click();await b('关闭活动目录').click({position:{x:375,y:400}});await expect(directory).toHaveCount(0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.equal((await saved()).activeId,current);
  });
  await t.test('旧记录保留无时间标记；较多根活动分批展示并可定位旧消息',async()=>{
    await page.setViewportSize({width:1600,height:1000});
    await page.evaluate(({key,root})=>{
      const s=JSON.parse(localStorage.getItem(key));delete s.activities.find(a=>a.id===root).startedAt;
      s.notices=s.notices.filter(n=>n.startId!==root);
      for(let i=0;i<25;i++){
        const id='OLDER-'+i;
        s.activities.push({id,kind:'答疑',title:'历史问题 '+i,startedAt:new Date(2026,0,1,i).toISOString(),status:'已结束',state:'结束'});
        s.turns.push({question:'历史提问 '+i,reply:'历史回答 '+i,activityId:id});
      }
      s.directoryOpen=true;localStorage.setItem(key,JSON.stringify(s));
    },{key,root});await page.reload();
    await expect(b('加载更早活动')).toBeVisible();await expect(locate(root)).toHaveCount(0);
    await b('加载更早活动').click();await expect(locate(root)).toContainText('时间未记录');
    await locate(root).click();await expect(page.getByRole('log').locator('article').first()).toHaveClass(/activity-highlight/);
    assert.equal((await saved()).activeId,current);assert.deepEqual(errors,[]);assert.deepEqual(api,[]);
  });
});
