import { test, expect, type Page } from '@playwright/test';
const entry='/structure.html?role=student#/home';
async function scale(page:Page,n='300'){
 await page.getByRole('button',{name:'首页情境',exact:true}).click();
 await page.getByLabel('章节目录规模',{exact:true}).selectOption(n);
 await page.getByRole('button',{name:'首页情境',exact:true}).click();
}
async function directory(page:Page){await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'学习情况',exact:true}).click();}

test('overview stays bounded at 3, 30 and 300 chapters and synthetic rows never acquire judgments',async({page})=>{
 await page.goto(entry);
 for(const n of ['3','30','300']){
  await scale(page,n);
  await expect(page.locator('.recent-chapter')).toHaveCount(1);
  await expect(page.locator('.catalog-row')).toHaveCount(0);
  await expect(page.getByRole('region',{name:'学习情况摘要'})).not.toContainText('目录已收录');
 }
 await directory(page);
 await expect(page.locator('.catalog-row')).toHaveCount(12);
 await expect(page.getByRole('status')).toContainText('共 300 章');
 await page.getByLabel('查看范围',{exact:true}).selectOption('unknown');
 await expect(page.getByRole('status')).toContainText('共 297 章');
 await expect(page.locator('.catalog-row').first()).toContainText('内容准备中 · 尚无学习评价');
 await page.locator('.catalog-row').first().click();
 await expect(page.getByRole('heading',{name:'内容准备中',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'请求本章讲解',exact:true})).toHaveCount(0);
 await expect(page.locator('.counts')).toHaveCount(0);
});

test('find a repeated chapter title by book and unit and preserve query through detail and refresh',async({page})=>{
 await page.goto(entry);await scale(page);await directory(page);
 await page.getByLabel('查找章节',{exact:true}).fill('综合应用');
 await page.getByRole('button',{name:'搜索',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('共 30 章');
 await page.getByLabel('分册',{exact:true}).focus();
 await page.getByLabel('分册',{exact:true}).selectOption('示例分册 3');
 await expect(page.getByLabel('分册',{exact:true})).toBeFocused();
 await page.getByLabel('单元',{exact:true}).selectOption('单元 10');
 await expect(page.locator('.catalog-row')).toHaveCount(1);
 await expect(page.locator('.catalog-row')).toContainText('示例分册 3 / 单元 10 / 第 1 节');
 await page.locator('.catalog-row').click();
 await expect(page.locator('h1')).toHaveText('综合应用');
 await page.reload();
 await page.getByRole('button',{name:'← 返回章节目录',exact:true}).click();
 await expect(page.getByLabel('查找章节',{exact:true})).toHaveValue('综合应用');
 await expect(page.getByLabel('单元',{exact:true})).toHaveValue('单元 10');
 await expect(page.locator('.catalog-row')).toHaveCount(1);
 await page.getByRole('button',{name:'清除筛选',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('共 300 章');
});

test('page, scroll position, keyboard focus and separate drafts survive chapter round trip',async({page})=>{
 await page.setViewportSize({width:834,height:1112});await page.goto(entry);await scale(page);await directory(page);
 await page.getByRole('button',{name:'下一页',exact:true}).click();
 const listUrl=page.url();
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('我的目录问题');
 const row=page.locator('.catalog-row').nth(8);const id=await row.getAttribute('data-chapter');
 await row.scrollIntoViewIfNeeded();const before=await page.locator('main').evaluate(e=>e.scrollTop);
 await row.focus();await page.keyboard.press('Enter');
 await expect(page.locator('h1')).toBeFocused();
 await expect(page.locator('h1')).toBeInViewport();
 await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toHaveValue('');
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('这一章的问题');
 await page.getByRole('button',{name:'← 返回章节目录',exact:true}).click();
 await expect(page).toHaveURL(listUrl);
 await expect(page.locator(`[data-chapter="${id}"]`)).toBeFocused();
 await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toHaveValue('我的目录问题');
 expect(Math.abs(await page.locator('main').evaluate(e=>e.scrollTop)-before)).toBeLessThan(4);
 await page.locator(`[data-chapter="${id}"]`).click();
 await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toHaveValue('这一章的问题');
 await page.goBack();await expect(page).toHaveURL(listUrl);
});

test('search with no result, invalid chapter and absent evaluation offer a clear recovery',async({page})=>{
 await page.goto(entry);await scale(page);await directory(page);
 await page.getByLabel('查找章节',{exact:true}).fill('不存在的章节');await page.getByRole('button',{name:'搜索',exact:true}).click();
 await expect(page.getByRole('heading',{name:'没有找到符合条件的章节'})).toBeVisible();
 await expect(page.getByRole('navigation',{name:'章节分页'})).toHaveCount(0);
 await page.getByRole('button',{name:'查看全部章节',exact:true}).click();
 await expect(page.locator('.catalog-row')).toHaveCount(12);
 await page.goto('/structure.html?role=student#/status?chapter=missing');
 await expect(page.locator('h1')).toHaveText('找不到这个章节');
 await page.getByRole('button',{name:'返回章节目录',exact:true}).click();
 await page.getByRole('button',{name:'首页情境',exact:true}).click();
 await page.getByLabel('首页参考资料',{exact:true}).selectOption('none');
 await page.getByRole('button',{name:'首页情境',exact:true}).click();
 await directory(page);await page.getByLabel('查看范围',{exact:true}).selectOption('attention');
 await expect(page.getByRole('status')).toContainText('共 0 章');
 await page.getByLabel('查看范围',{exact:true}).selectOption('unknown');
 await expect(page.getByRole('status')).toContainText('共 300 章');
});

test('recent overview deduplicates chapters and bounds ongoing activities',async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('deermind-structure-v1',JSON.stringify({
  version:1,studentSpace:'school',parentChild:'S0001',parentSpace:'school',issues:[],drafts:{},messages:{},access:{},
  sessions:Array.from({length:20},(_,i)=>({id:`LIVE-${i}`,learner:'S0001',space:'school',chapter:i%2?'circle':'fractions',segment:0,status:'learning',answer:'',submitted:false,endedReason:'',date:'2026-10-17',updatedAt:100+i}))
 })));
 await page.goto(entry);
 await expect(page.locator('.recent-chapter')).toHaveCount(1);
 await expect(page.locator('.recent-chapter').first()).toContainText('圆');
 await expect(page.getByRole('button',{name:'继续这次学习',exact:false})).toHaveCount(1);
 await page.getByText('还有 19 项学习可以继续',{exact:true}).click();
 await expect(page.locator('.home-other .record-row')).toHaveCount(3);
 await expect(page.getByRole('button',{name:'查看全部学习活动 →',exact:true})).toBeVisible();
 await directory(page);await page.getByLabel('查看范围',{exact:true}).selectOption('activity');
 await expect(page.locator('.catalog-row')).toHaveCount(2);
});

for(const viewport of [{width:1280,height:900},{width:834,height:1112},{width:390,height:844},{width:1024,height:600}]){
 test(`long names and filters remain operable at ${viewport.width}x${viewport.height}`,async({page})=>{
  await page.setViewportSize(viewport);await page.goto(entry);await scale(page);await directory(page);
  if(viewport.width===390)await expect(page.locator('.catalog-row').first()).toBeInViewport();
  await page.getByLabel('查找章节',{exact:true}).fill('多种表示');await page.getByRole('button',{name:'搜索',exact:true}).click();
  await expect(page.locator('.catalog-row').first()).toContainText('从多种表示方式理解数量关系');
  await page.locator('.catalog-row').first().click();await expect(page.locator('h1')).toBeInViewport();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const main=await page.locator('main').boundingBox(),composer=await page.locator('.composer').boundingBox();
  expect(main!.y+main!.height).toBeLessThanOrEqual(composer!.y+1);
  await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toBeInViewport();
  await page.getByRole('button',{name:'← 返回章节目录',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('共 30 章');
 });
}
