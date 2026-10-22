import { test, expect, type Page } from '@playwright/test';
const entry=(path='chapter?chapter=fractions',role='student')=>`/legacy-structure.html?role=${role}&preview=scripted#/${path}`;
async function begin(page:Page){await page.goto(entry());await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();return page.url();}
async function scenario(page:Page,name:string){await page.getByRole('button',{name:'教学情境',exact:true}).click();await page.getByRole('button',{name,exact:true}).click();}

test('quick and support paths diverge inside the same surface without claiming learner performance',async({page})=>{
 const url=await begin(page);await scenario(page,'载入理解较快情境');
 await expect(page.getByText('明白了。如果问乙比甲少，就应该用 3÷12，因为这次和甲比。',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'看看 12 张的图示',exact:true})).toHaveCount(0);
 await expect(page.getByText('这段反馈只对应上面的示例表达，没有评价本轮真实输入。')).toBeVisible();
 await page.getByRole('button',{name:'检查一下这次理解',exact:true}).click();
 await expect(page.getByRole('region',{name:'检查安排'})).toBeVisible();await expect(page).toHaveURL(url);
 await page.getByRole('button',{name:'继续交流，暂不检查',exact:true}).click();
 await page.getByRole('button',{name:'这次先到这里',exact:true}).click();await expect(page).toHaveURL(url);
 await begin(page);const second=page.url();await scenario(page,'载入基础回补情境');
 await expect(page.getByRole('heading',{name:'先把“三张占九张多少”讲清楚'})).toBeVisible();
 await page.getByRole('button',{name:'看看 12 张的图示',exact:true}).click();
 await expect(page.getByRole('figure',{name:'把 12 张卡片分成 4 组，每组 3 张，突出其中 1 组'})).toBeVisible();
 await page.getByRole('button',{name:'回到原题',exact:true}).click();await expect(page).toHaveURL(second);
 await page.reload();await expect(page.getByRole('heading',{name:'相差量没变，比较标准变了'})).toBeVisible();
 const stored=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-structure-v1')!));
 expect(stored.sessions).toHaveLength(2);expect(stored.sessions.every((s:any)=>!s.submitted&&s.answer==='')).toBeTruthy();
});

test('free messages appear in order, survive refresh, and cannot inject HTML or drive a scripted reply',async({page})=>{
 await begin(page);await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('<img src=x onerror="window.injected=true"> 我已经会了');
 await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('.student-turn').last()).toContainText('<img src=x');
 await expect(page.locator('.student-turn img')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'对话历史',exact:true})).toHaveCount(0);
 await expect(page.getByText('相差量没变，比较标准变了',{exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'看看 12 张的图示',exact:true}).click();
 const ordered=await page.locator('.conversation-turns article').allTextContents();
 expect(ordered.findIndex(t=>t.includes('<img src=x'))).toBeLessThan(ordered.findIndex(t=>t.includes('同样的 3 张，放进 12 张里呢')));
 await page.reload();await expect(page.locator('.student-turn')).toHaveCount(1);
 await expect(page.locator('.student-turn')).toContainText('尚未处理');
});

test('embedded check restores its draft, hides earlier help and ends before showing requested teaching',async({page})=>{
 const url=await begin(page);
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('之前的解释里有 3÷9=1/3');await page.getByRole('button',{name:'发送',exact:true}).click();
 await page.getByRole('button',{name:'检查一下这次理解',exact:true}).click();await page.getByRole('button',{name:'开始检查',exact:true}).click();
 await expect(page).toHaveURL(url);await expect(page.locator('.card-groups')).toHaveCount(0);await expect(page.getByText('之前的解释里有 3÷9=1/3',{exact:true})).toHaveCount(0);
 await page.getByLabel('检查作答',{exact:true}).fill('还没完成的草稿');await page.reload();
 await expect(page.getByLabel('检查作答',{exact:true})).toHaveValue('还没完成的草稿');
 await page.getByRole('button',{name:'需要讲解，结束检查',exact:true}).click();await expect(page).toHaveURL(url);
 await expect(page.getByRole('heading',{name:'请求讲解，先结束检查',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'一起看这道检查题',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'提交本次检查',exact:true})).toHaveCount(0);
 const stored=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-structure-v1')!).sessions[0]);
 expect(stored.submitted).toBeFalsy();expect(stored.answer).toBe('还没完成的草稿');expect(stored.status).toBe('ended');expect(stored.postHelpShown).toBeTruthy();
 await page.reload();await expect(page.getByRole('button',{name:'开始检查',exact:true})).toHaveCount(0);
});

test('practice stays distinct from a check and is available in the parent record',async({page})=>{
 const url=await begin(page);await page.getByRole('button',{name:'一起练一练',exact:true}).click();
 await page.getByLabel('练习作答',{exact:true}).fill('3÷12，标准是甲的12张。');await page.reload();
 await expect(page.getByLabel('练习作答',{exact:true})).toHaveValue('3÷12，标准是甲的12张。');
 await page.getByRole('button',{name:'提交练习',exact:true}).click();await expect(page).toHaveURL(url);
 await expect(page.getByText('作答已保留，当前没有运行评分。刚才的讲解背景一并保留，不能据此宣布独立掌握。')).toBeVisible();
 await page.getByRole('button',{name:'这次先到这里',exact:true}).click();
 await page.goto(entry('overview','parent'));await page.getByRole('button',{name:/本次讲解与检查/}).click();
 await expect(page.getByRole('heading',{name:'讲解中的练习 · 尚未判定'})).toBeVisible();
 await expect(page.getByText('3÷12，标准是甲的12张。',{exact:true})).toBeVisible();
 await expect(page.getByText('没有提交作答',{exact:true})).toBeVisible();
});

test('new messages do not pull a reader away from an earlier explanation',async({page})=>{
 await page.setViewportSize({width:834,height:850});await begin(page);await scenario(page,'载入基础回补情境');
 await page.getByRole('button',{name:'看看 12 张的图示',exact:true}).click();await page.getByRole('button',{name:'回到原题',exact:true}).click();
 await page.locator('main').evaluate(el=>el.scrollTop=0);
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('先问前面那幅图');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.getByRole('button',{name:'有新内容，查看最新位置 ↓',exact:true})).toBeVisible();
 expect(await page.locator('main').evaluate(el=>el.scrollTop)).toBeLessThan(150);
 await page.getByRole('button',{name:'有新内容，查看最新位置 ↓',exact:true}).click();
 await expect(page.locator('.student-turn').last()).toBeInViewport();
});

test('embedded controls and reserved composer remain usable on tablet and narrow screen',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await begin(page);await scenario(page,'载入基础回补情境');
 for(const [width,height] of [[834,600],[430,932]]){
  await page.setViewportSize({width,height});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const main=await page.locator('main').boundingBox(),composer=await page.locator('.composer').boundingBox();
  expect(main!.y+main!.height).toBeLessThanOrEqual(composer!.y+1);
  await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toBeInViewport();
 }
 expect(errors).toEqual([]);
});
