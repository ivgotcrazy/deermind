import { test, expect, type Page } from '@playwright/test';
const entry=(role='student',path='')=>`/legacy-structure.html?role=${role}&preview=scripted#/${path}`;
async function lesson(page:Page,chapter='fractions'){
 await page.goto(entry('student',`chapter?chapter=${chapter}`));
 await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();
 await page.getByRole('button',{name:'检查一下这次理解',exact:true}).click();
 await page.getByRole('button',{name:'开始检查',exact:true}).click();
}

test('one actual submission flows through parent review and scoped administrator inspection',async({page})=>{
 await lesson(page);
 await page.getByLabel('检查作答',{exact:true}).fill('比较标准是小雨的12张，3÷12=1/4。');
 await page.getByRole('button',{name:'提交本次检查',exact:true}).click();
 await expect(page.getByRole('heading',{name:'检查已提交',exact:true})).toBeVisible();
 await page.goto(entry('parent','overview'));
 await page.getByRole('button',{name:/本次讲解与检查/}).click();
 await expect(page.getByText('小青有 15 张卡片，小雨有 12 张。小青比小雨多几分之几？请说明比较标准。',{exact:true})).toBeVisible();
 await expect(page.locator('blockquote')).toContainText('比较标准是小雨');
 await page.getByRole('button',{name:'提出复核',exact:true}).click();
 await page.getByLabel('复核说明').fill('请核对本次作答为什么还没有评价。');
 await page.getByRole('button',{name:'提交复核事项',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('已提交');
 await page.goto(entry('admin'));
 await page.getByRole('button',{name:/请核对本次作答为什么还没有评价/}).click();
 await expect(page.getByRole('heading',{name:'明确本次查看用途'})).toBeVisible();
 await expect(page.getByText('比较标准是小雨的12张，3÷12=1/4。',{exact:true})).toHaveCount(0);
 await page.getByLabel('查看用途').fill('复核家长提交的本次结果事项');
 await page.getByRole('button',{name:'记录用途，进入案例'}).click();
 await page.getByRole('navigation',{name:'案例详情'}).getByRole('button',{name:'交互过程',exact:true}).click();
 await expect(page.locator('blockquote')).toContainText('比较标准是小雨');
 await page.getByRole('button',{name:'评价依据',exact:true}).click();
 await expect(page.getByText('此活动没有运行真实 Evaluation。不会根据页面操作生成 Evidence 或 Belief。')).toBeVisible();
 await page.getByRole('button',{name:'处理记录',exact:true}).click();
 await page.getByLabel('人工处理意见').fill('本稿没有运行评价，保留未决；不修改学习者状态。');
 await page.getByRole('button',{name:'保存人工意见'}).click();
 await expect(page.getByRole('status')).toContainText('没有修改模型');
 await page.goto(entry('parent','overview'));
 await page.getByRole('button',{name:/本次讲解与检查/}).click();
 await expect(page.getByText(/处理意见：本稿没有运行评价/)).toBeVisible();
});

test('record filters, pagination, and browser back retain the query context',async({page})=>{
 await page.goto(entry('student','records?chapter=fractions&source=检测&p=2'));
 await expect(page.locator('.record-list .record-row')).toHaveCount(12);
 const before=page.url(); const first=await page.locator('.record-list .record-row').first().innerText();
 await page.locator('.record-list .record-row').first().click();
 await page.getByRole('button',{name:'← 返回原位置'}).click();
 await expect(page).toHaveURL(before);
 await expect(page.locator('.record-list .record-row').first()).toHaveText(first,{useInnerText:true});
 await page.getByLabel('查找记录',{exact:true}).fill('不存在的内容');
 await expect(page.getByRole('heading',{name:'当前条件下没有记录'})).toBeVisible();
});

test('large admin directories are bounded and details retain original filters',async({page})=>{
 await page.goto(entry('admin','users?type=学生&p=3'));
 await expect(page.locator('tbody tr')).toHaveCount(20);
 await expect(page.getByText('当前条件：1,000 条 · 每页 20 条')).toBeVisible();
 const before=page.url();await page.locator('tbody tr').first().getByRole('button').click();
 await page.getByRole('button',{name:'← 返回目录，保留筛选'}).click();
 await expect(page).toHaveURL(before);
 await page.getByLabel('查找对象').fill('S0701');
 await expect(page.locator('tbody tr')).toHaveCount(1);
 await page.locator('tbody tr').first().getByRole('button').click();
 await expect(page.locator('h1')).toHaveText('陈同学 141');
 await page.locator('.record-row').first().click();
 await expect(page.getByRole('heading',{name:'明确本次查看用途'})).toBeVisible();
 await page.goto(entry('admin','models'));
 await expect(page.getByText('5,000 条',{exact:true})).toBeVisible();
 await expect(page.locator('tbody tr')).toHaveCount(20);
});

test('parent drafts and records are isolated by child and space',async({page})=>{
 await page.goto(entry('parent','overview'));
 await page.getByLabel('家长咨询输入',{exact:true}).fill('林同学校内咨询草稿');
 await page.getByLabel('当前孩子',{exact:true}).selectOption('S0042');
 await expect(page.getByLabel('家长咨询输入',{exact:true})).toHaveValue('');
 await page.getByLabel('家长咨询输入',{exact:true}).fill('周同学草稿');
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('external');
 await expect(page.getByRole('heading',{name:'还没有本空间的学习评价'})).toBeVisible();
 await expect(page.getByLabel('家长咨询输入',{exact:true})).toHaveValue('');
 await page.getByLabel('当前孩子',{exact:true}).selectOption('S0001');
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('school');
 await expect(page.getByLabel('家长咨询输入',{exact:true})).toHaveValue('林同学校内咨询草稿');
 await page.goto(entry('parent','record?id=R-S0042-1'));
 await expect(page.getByRole('heading',{name:'当前范围内没有这条内容'})).toBeVisible();
});

test('active checks cannot route into teaching, ended checks cannot reopen, parents cannot enter student actions',async({page})=>{
 await lesson(page,'circle');
 const url=page.url();const id=new URLSearchParams(url.split('?').at(-1)).get('id')!;
 await expect(page.getByText('一个圆的直径是 10 厘米，它的半径是多少？为什么？')).toBeVisible();
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'教材',exact:true}).click();
 await expect(page).toHaveURL(url);
 await page.getByRole('button',{name:'需要讲解，结束检查'}).click();
 await page.goto(entry('student',`prepare?id=${id}`));
 await expect(page.getByRole('button',{name:'开始检查',exact:true})).toHaveCount(0);
 await page.goto(entry('parent',`lesson?id=${id}`));
 await expect(page.getByRole('heading',{name:'当前范围内没有这条内容'})).toBeVisible();
 await expect(page.getByRole('button',{name:'提交本次检查'})).toHaveCount(0);
});

test('composer does not auto-open history or pretend to execute free text',async({page})=>{
 await page.goto(entry());
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('讲一下分数的应用');
 await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('尚未理解或执行请求');
 await expect(page.locator('.message-history')).toHaveCount(0);
 await page.getByRole('button',{name:'对话历史',exact:true}).click();
 await expect(page.locator('.message-history')).toContainText('讲一下分数的应用');
 await page.reload();
 await page.getByRole('button',{name:'对话历史',exact:true}).click();
 await expect(page.locator('.message-history')).toContainText('讲一下分数的应用');
});

for(const [role,width,height,path] of [['student',834,1112,'home'],['parent',430,932,'overview'],['admin',1440,1000,'users']] as const){
 test(`${role} layout at ${width}px keeps navigation and current input usable`,async({page})=>{
  await page.setViewportSize({width,height});const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(entry(role,path));
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await expect(page.locator('h1')).toBeVisible();
  if(role!=='admin')await expect(page.getByLabel(role==='parent'?'家长咨询输入':'向 DeerMind 提问',{exact:true})).toBeInViewport();
  expect(errors).toEqual([]);
 });
}
