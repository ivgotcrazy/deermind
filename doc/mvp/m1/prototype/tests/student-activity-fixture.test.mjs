import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium, expect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

test('预置活动森林：直接可见、逐项定位、隔离保留原有记录',async t=>{
  const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch();t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const base='http://127.0.0.1:'+server.address().port;
  const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[],api=[];
  page.on('pageerror',e=>errors.push(e.message));await page.route('**/api/**',r=>{api.push(r.request().url());return r.abort();});
  const personalKey='deermind-m1-student-trial-space-v1',demoKey='deermind-m1-student-activity-forest-demo-v1';
  const saved=()=>page.evaluate(key=>JSON.parse(localStorage.getItem(key)),demoKey);
  const directory=page.getByLabel('活动目录',{exact:true});
  await mkdir('test-results/student-activity-fixture',{recursive:true});

  await t.test('空浏览器直接显示四棵活动树和嵌套对话，无需创建空间',async()=>{
    await page.goto(base+'/student/');
    await expect(directory).toBeVisible();await expect(page.getByRole('log')).toBeVisible();
    await expect(page.getByRole('heading',{name:'创建学习空间'})).toHaveCount(0);
    await expect(page.locator('.mast')).toContainText('活动森林示例 · Mock');
    const s=await saved();assert.equal(s.activities.filter(a=>!a.parentId).length,4);
    assert.equal(s.activities.filter(a=>a.status==='进行中').length,1);
    assert.equal(s.activeId,'DEMO-BRACKET');
    for(const a of s.activities){
      assert.ok(s.turns.some(turn=>turn.activityId===a.id));
      assert.ok(s.notices.some(n=>n.startId===a.id));
      if(a.parentId)assert.ok(s.activities.some(parent=>parent.id===a.parentId));
    }
    assert.equal(await page.evaluate(key=>localStorage.getItem(key),personalKey),null);
    await page.screenshot({path:'test-results/student-activity-fixture/01-open-forest.png'});
  });
  await t.test('全部活动均可定位；收起展开、回看不改变当前活动或已结束检测',async()=>{
    const before=await saved();
    for(const a of before.activities){
      await directory.locator(`[data-activity="${a.id}"]`).click();
      await expect(page.locator('.review-banner')).toContainText(a.title);
      const start=page.locator(`[data-activity-start="${a.id}"]`);
      await expect(start).toHaveClass(/activity-highlight/);
      const visible=await start.evaluate(el=>{
        const anchor=el.getBoundingClientRect(),viewport=el.closest('.transcript').getBoundingClientRect();
        return anchor.top>=viewport.top&&anchor.bottom<=viewport.bottom;
      });
      assert.ok(visible,'anchor must be visible: '+a.id);
      assert.equal((await saved()).activeId,before.activeId);
    }
    await directory.getByRole('button',{name:'收起子活动：用新题检查四分之一',exact:true}).click();
    await expect(directory.locator('[data-activity="DEMO-BASE"]')).toHaveCount(0);
    await directory.getByRole('button',{name:'展开子活动：用新题检查四分之一',exact:true}).click();
    await directory.locator('[data-activity="DEMO-BASE"]').click();
    await expect(page.getByRole('button',{name:'提交作答',exact:true})).toHaveCount(0);
    assert.deepEqual((await saved()).activities,before.activities);
    assert.deepEqual((await saved()).turns,before.turns);
    await page.screenshot({path:'test-results/student-activity-fixture/02-nested-history.png'});
    await page.getByRole('button',{name:'回到当前活动',exact:true}).click();
    await page.getByRole('button',{name:'回到原来的主线',exact:true}).click();
    assert.equal((await saved()).activeId,'DEMO-CURRENT');
    await page.reload();assert.equal((await saved()).activeId,'DEMO-CURRENT');
    assert.equal((await saved()).activities.length,before.activities.length);
  });
  await t.test('已有个人记录保持原样，入口可切回并恢复草稿',async()=>{
    const original=JSON.stringify({bookId:'BNU-6A',targetId:'TARGET-M1-QUARTER-SEPARATE',chapter:'分数的应用（一）',page:'50',layout:'split',paperPosition:0,chatPosition:-1,draft:'原来未发送的内容',turns:[{activityId:'OLD-1',question:'这是原有聊天',reply:'原有回复'}],activities:[{id:'OLD-1',kind:'自由交谈',title:'原有活动',status:'进行中',state:'回应中'}],activeId:'OLD-1',notices:[],directoryOpen:true,expandedActivities:[]});
    await page.evaluate(({key,value})=>localStorage.setItem(key,value),{key:personalKey,value:original});
    await page.goto(base+'/student/');
    await expect(directory.locator('[data-activity="DEMO-CURRENT"]')).toBeVisible();
    await page.locator('#student-prompt').fill('示例中的草稿');
    await page.reload();await expect(page.locator('#student-prompt')).toHaveValue('示例中的草稿');
    assert.equal(await page.evaluate(key=>localStorage.getItem(key),personalKey),original);
    await page.getByRole('link',{name:'查看原有记录',exact:true}).click();
    await expect(page.locator('#student-prompt')).toHaveValue('原来未发送的内容');
    await expect(page.getByRole('log')).toContainText('这是原有聊天');
    await expect(directory.locator('[data-activity="DEMO-CURRENT"]')).toHaveCount(0);
    await expect(directory.locator('[data-activity="OLD-1"]')).toBeVisible();
    await expect(page.locator('.reader footer')).toContainText('50');
    await page.getByRole('link',{name:'查看活动示例',exact:true}).click();
    await expect(page.locator('#student-prompt')).toHaveValue('示例中的草稿');
  });
  await t.test('窄屏首次打开也看到目录，选择后关闭并定位，无横向溢出',async()=>{
    const mobile=await browser.newPage({viewport:{width:390,height:844}});
    mobile.on('pageerror',e=>errors.push(e.message));
    await mobile.goto(base+'/student/');
    await expect(mobile.getByLabel('活动目录',{exact:true})).toBeVisible();
    await mobile.screenshot({path:'test-results/student-activity-fixture/03-mobile-open.png'});
    await mobile.locator('[data-activity="DEMO-BRACKET"]').click();
    await expect(mobile.getByLabel('活动目录',{exact:true})).toHaveCount(0);
    await expect(mobile.locator('.review-banner')).toContainText('括号里的 1 代表什么');
    await mobile.getByRole('button',{name:'展开活动目录',exact:true}).click();
    await expect(mobile.getByLabel('活动目录',{exact:true})).toBeVisible();
    assert.equal(await mobile.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await mobile.close();
  });
  assert.deepEqual(errors,[]);assert.deepEqual(api,[]);
});
