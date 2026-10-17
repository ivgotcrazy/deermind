import { test, expect, type Page } from '@playwright/test';
const entry='/structure.html?role=student&preview=scripted#/status';
const dialog=(page:Page)=>page.getByRole('dialog',{name:'更新课堂进度',exact:true});
const progress=(page:Page)=>page.getByRole('region',{name:'课堂进度',exact:true});
const stored=(page:Page)=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-structure-v1')!));
const homeEntry='/structure.html?role=student&preview=scripted#/home';
async function saveFractions(page:Page){
 await progress(page).getByRole('button',{name:'设置课堂进度',exact:true}).click();
 await dialog(page).getByRole('checkbox',{name:/分数的应用$/}).check();
 await dialog(page).getByRole('button',{name:'保存课堂进度',exact:true}).click();
}

test('confirmed classroom context persists, never changes judgments, and does not infer earlier chapters',async({page})=>{
 await page.goto(entry);
 const judgments=await page.locator('.catalog-state').allTextContents();
 await expect(progress(page)).toContainText('尚未填写');
 await expect(page.locator('.classroom-marker')).toHaveCount(0);
 await progress(page).getByRole('button',{name:'设置课堂进度',exact:true}).click();
 await expect(dialog(page).getByRole('button',{name:'保存课堂进度',exact:true})).toBeDisabled();
 await dialog(page).getByRole('checkbox',{name:/分数的应用$/}).check();
 await dialog(page).getByLabel('小节或补充说明（选填）').fill('分数的应用（二），刚开始讲。');
 await dialog(page).getByRole('button',{name:'保存课堂进度',exact:true}).click();
 await expect(page.locator('[data-chapter=fractions] .classroom-marker')).toHaveText('课堂正在学');
 await expect(page.locator('[data-chapter=circle] .classroom-marker')).toHaveCount(0);
 expect(await page.locator('.catalog-state').allTextContents()).toEqual(judgments);
 let data=await stored(page);expect(data.sessions).toHaveLength(0);expect(data.classroomProgress).toHaveLength(1);
 expect(data.classroomProgress[0]).toMatchObject({learner:'S0001',space:'school',source:'student-confirmed',material:'BNU6A-PROTOTYPE',status:'reported'});
 await page.reload();await expect(progress(page)).toContainText('分数的应用');
 await progress(page).getByRole('button',{name:'更新课堂进度',exact:true}).click();
 await expect(dialog(page).getByLabel('小节或补充说明（选填）')).toHaveValue('分数的应用（二），刚开始讲。');
 await dialog(page).getByRole('checkbox',{name:/圆$/}).check();await dialog(page).getByRole('button',{name:'取消',exact:true}).click();
 expect((await stored(page)).classroomProgress).toHaveLength(1);
 await expect(page.locator('.classroom-marker')).toHaveCount(1);
 await expect(progress(page).getByRole('button',{name:'更新课堂进度',exact:true})).toBeFocused();
 await progress(page).getByRole('button',{name:'更新课堂进度',exact:true}).click();
 await dialog(page).getByRole('checkbox',{name:/比的认识$/}).check();await dialog(page).getByRole('button',{name:'保存课堂进度',exact:true}).click();
 await expect(page.locator('.classroom-marker')).toHaveCount(2);
 await expect(page.locator('[data-chapter=circle] .classroom-marker')).toHaveCount(0);
 expect(await page.locator('.catalog-state').allTextContents()).toEqual(judgments);
});

test('unknown is explicit, prior reports remain inspectable, and Escape discards edits',async({page})=>{
 await page.goto(entry);await saveFractions(page);
 await progress(page).getByRole('button',{name:'更新课堂进度',exact:true}).click();
 await dialog(page).getByRole('radio',{name:'暂不确定',exact:true}).check();
 await page.keyboard.press('Escape');await expect(dialog(page)).not.toBeVisible();await expect(progress(page)).toContainText('分数的应用');
 await progress(page).getByRole('button',{name:'更新课堂进度',exact:true}).click();
 await dialog(page).getByRole('radio',{name:'暂不确定',exact:true}).check();
 await dialog(page).getByRole('button',{name:'保存课堂进度',exact:true}).click();
 await expect(progress(page)).toContainText('暂不确定');await expect(page.locator('.classroom-marker')).toHaveCount(0);
 await page.reload();await expect(progress(page)).toContainText('暂不确定');
 await progress(page).getByRole('button',{name:'更新课堂进度',exact:true}).click();
 await dialog(page).getByText('查看更新记录（2 次）',{exact:true}).click();
 await expect(dialog(page).locator('.classroom-history')).toContainText('分数的应用');
 expect((await stored(page)).classroomProgress.map((p:any)=>p.status)).toEqual(['reported','unknown']);
});

test('parents only inspect the matching learner; other spaces and learners never inherit classroom context',async({page})=>{
 await page.goto(entry);await saveFractions(page);
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('external');await expect(progress(page)).toHaveCount(0);
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('school');await expect(progress(page)).toContainText('分数的应用');
 await page.goto('/structure.html?role=parent#/overview');await expect(progress(page)).toContainText('分数的应用');
 await progress(page).getByRole('button',{name:'查看课堂进度',exact:true}).click();
 const viewer=page.getByRole('dialog',{name:'课堂进度',exact:true});await expect(viewer).toBeVisible();
 await expect(viewer.getByRole('checkbox')).toHaveCount(0);await expect(viewer.getByRole('button',{name:'保存课堂进度'})).toHaveCount(0);
 await viewer.getByRole('button',{name:'关闭',exact:true}).click();
 await page.getByLabel('当前孩子',{exact:true}).selectOption('S0042');await expect(progress(page)).toContainText('尚未填写');
 await expect(page.locator('.classroom-marker')).toHaveCount(0);expect((await stored(page)).classroomProgress).toHaveLength(1);
});

test('large chapter picker is searchable, bounded and retains current catalogue filters',async({page})=>{
 await page.goto(entry);await page.getByRole('button',{name:'首页情境',exact:true}).click();await page.getByLabel('章节目录规模',{exact:true}).selectOption('300');await page.getByRole('button',{name:'首页情境',exact:true}).click();
 await page.getByRole('button',{name:'下一页',exact:true}).click();const beforeUrl=page.url();
 await progress(page).getByRole('button',{name:'设置课堂进度',exact:true}).click();
 await expect(dialog(page).getByRole('checkbox')).toHaveCount(8);
 await dialog(page).getByLabel('查找课堂章节',{exact:true}).fill('示例分册 3 单元 10 综合应用');
 await expect(dialog(page).getByRole('checkbox')).toHaveCount(1);
 await dialog(page).getByRole('checkbox').check();await dialog(page).getByRole('button',{name:'保存课堂进度',exact:true}).click();
 await expect(page).toHaveURL(beforeUrl);await expect(progress(page)).toContainText('综合应用');
 const data=await stored(page);expect(data.classroomProgress[0].chapters[0].path).toBe('示例分册 3 / 单元 10 / 第 1 节');
 await progress(page).getByRole('button',{name:'更新课堂进度',exact:true}).click();
 await expect(dialog(page).locator('.classroom-selection')).toContainText('综合应用');
 await dialog(page).getByRole('button',{name:'取消',exact:true}).click();
 await page.goto(`${entry}?chapter=${data.classroomProgress[0].chapters[0].id}`);
 await expect(page.locator('.chapter-detail-page .classroom-marker')).toHaveText('课堂正在学');
 await expect(page.getByRole('heading',{name:'内容准备中',exact:true})).toBeVisible();
});

test('home exposes classroom context and updates the same record without changing the DeerMind learning topic',async({page})=>{
 await page.goto(homeEntry);
 await expect(progress(page).getByRole('heading',{name:'学校现在学到哪里？',exact:true})).toBeVisible();
 await saveFractions(page);
 await expect(progress(page).getByRole('heading',{name:'分数的应用',exact:true})).toBeVisible();
 await expect(progress(page)).toContainText('上次确认');
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'学习情况',exact:true}).click();
 await expect(page.locator('[data-chapter=fractions] .classroom-marker')).toHaveText('课堂正在学');
 await progress(page).getByRole('button',{name:'更新课堂进度',exact:true}).click();
 await dialog(page).getByRole('checkbox',{name:/分数的应用$/}).uncheck();
 await dialog(page).getByRole('checkbox',{name:/圆$/}).check();
 await dialog(page).getByRole('button',{name:'保存课堂进度',exact:true}).click();
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'首页',exact:true}).click();
 await expect(progress(page).getByRole('heading',{name:'圆',exact:true})).toBeVisible();
 await expect(page.getByRole('region',{name:'学习情况摘要'})).toContainText('分数的应用');
 expect((await stored(page)).sessions).toHaveLength(0);
 await page.reload();await expect(progress(page).getByRole('heading',{name:'圆',exact:true})).toBeVisible();
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('external');await expect(progress(page)).toHaveCount(0);
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('school');await expect(progress(page).getByRole('heading',{name:'圆',exact:true})).toBeVisible();
 await progress(page).getByRole('button',{name:'更新课堂进度',exact:true}).click();
 await dialog(page).getByRole('radio',{name:'暂不确定',exact:true}).check();
 await dialog(page).getByRole('button',{name:'保存课堂进度',exact:true}).click();
 await expect(progress(page).getByRole('heading',{name:'暂不确定',exact:true})).toBeVisible();
 await expect(progress(page)).not.toContainText('学校正在学');
});

for(const viewport of [{width:834,height:1112},{width:390,height:844},{width:1024,height:600}]){
 test(`progress editor keeps controls visible at ${viewport.width}x${viewport.height}`,async({page})=>{
  await page.setViewportSize(viewport);await page.goto(entry);
  await progress(page).getByRole('button',{name:'设置课堂进度',exact:true}).click();
  await expect(dialog(page).getByRole('button',{name:'取消',exact:true})).toBeInViewport();
  await expect(dialog(page).getByRole('button',{name:'保存课堂进度',exact:true})).toBeInViewport();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await dialog(page).getByRole('checkbox',{name:/分数的应用$/}).check();
  await dialog(page).getByRole('button',{name:'保存课堂进度',exact:true}).click();
  await expect(page.locator('[data-chapter=fractions] .classroom-marker')).toHaveText('课堂正在学');
  await page.goto(homeEntry);
  const main=await page.locator('main').boundingBox();
  const banner=await progress(page).boundingBox();
  expect(banner!.y).toBeGreaterThanOrEqual(main!.y);
  expect(banner!.y+banner!.height).toBeLessThanOrEqual(main!.y+main!.height);
  await expect(progress(page).getByRole('button',{name:'更新课堂进度',exact:true})).toBeInViewport();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 });
}
