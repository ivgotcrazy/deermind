import { test, expect, type Page } from '@playwright/test';
const entry=(path='home',role='student')=>`/legacy-structure.html?role=${role}&preview=scripted#/${path}`;
async function tools(page:Page){await page.getByRole('button',{name:'首页情境',exact:true}).click();}

test('student entry, chapter detail, and space isolation remain consistent',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/legacy-structure.html?role=student');
 await expect(page).toHaveURL(/#\/home$/);
 await expect(page.getByRole('heading',{name:'首页',exact:true})).toBeVisible();
 await expect(page.getByRole('navigation',{name:'主导航'}).getByRole('button')).toHaveText(['首页','学习情况','教材','学习记录']);
 const summary=page.getByRole('region',{name:'学习情况摘要'});
 await expect(summary).toContainText('近期关注');
 await expect(page.locator('.catalog-row')).toHaveCount(0);
 await expect(page.getByRole('region',{name:'学习活动统计'})).toBeVisible();
 await expect(page.locator('.status-totals')).toHaveCount(0);
 await expect(page.locator('.recent-chapter').filter({hasText:'分数的应用'})).toContainText('为什么用它作除数');
 await expect(page.locator('.recent-chapter')).toHaveCount(1);
 await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toBeInViewport();
 await page.goto(entry('home?chapter=fractions'));
 await expect(page).toHaveURL(/#\/status\?chapter=fractions$/);
 const detail=page.getByRole('region',{name:'分数的应用学习详情',exact:true});
 await expect(detail).toBeVisible();
 await expect(detail).toContainText('暂无可比较的学习评价');
 await expect(detail).toContainText('尚无可用于统计的已判定独立作答');
 await expect(detail.getByLabel('本章要求项数')).not.toBeVisible();
 await detail.getByText('查看 6 项学习要求及状态',{exact:true}).click();
 await expect(detail.getByLabel('本章要求项数').locator('b')).toHaveText(['2已达标','2需加强','2待确认']);
 await page.getByRole('button',{name:'查看本章记录',exact:false}).click();
 await expect(page).toHaveURL(/#\/records\?chapter=fractions/);
 await page.goBack();await expect(detail).toBeVisible();
 await page.getByRole('button',{name:'← 返回章节目录',exact:true}).click();
 await expect(detail).toHaveCount(0);
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('external');
 await expect(page).toHaveURL(/#\/status$/);
 await expect(page.locator('.status-totals')).toHaveCount(0);
 await expect(page.locator('.recent-chapter')).toHaveCount(0);
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('school');
 await expect(page.locator('.catalog-row')).toHaveCount(3);
 await expect(page.getByRole('region',{name:'学习活动统计'})).toHaveCount(0);
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'首页',exact:true}).click();
 await expect(page.locator('.recent-chapter')).toContainText('2 项要求待确认');
 expect(errors).toEqual([]);
});

test('home gives an inspectable reference and respects deferral without changing chapter states',async({page})=>{
 await page.goto(entry());
 const feedback=page.locator('.recent-chapter').filter({hasText:'分数的应用'});
 const before=await feedback.innerText();
 await expect(feedback).toContainText('2 项要求待确认');
 await page.getByRole('button',{name:'为什么建议这个？',exact:true}).click();
 await expect(page.getByRole('region',{name:'建议的参考依据'})).toContainText('提示后写出 3÷9=1/3');
 await page.getByRole('button',{name:'暂不安排',exact:true}).click();
 await expect(page.getByRole('button',{name:'从这里开始讲解',exact:false})).toHaveCount(0);
 await expect(feedback).toHaveText(before,{useInnerText:true});
 await page.reload();await expect(page.getByRole('button',{name:'重新查看建议',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'重新查看建议',exact:true}).click();
 await page.getByRole('button',{name:'从这里开始讲解',exact:false}).click();
 await expect(page).toHaveURL(/#\/lesson\?id=LIVE/);
 await expect(page.locator('h1')).toHaveText('为什么要除以比较标准？');
});

test('home resumes the most recently used activity, preserves draft and explains completed work',async({page})=>{
 await page.goto(entry('chapter?chapter=fractions'));
 await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();const older=page.url();
 await page.getByRole('button',{name:'看看 12 张的图示',exact:true}).click();
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('这里为什么要换标准？');
 await page.goto(entry('chapter?chapter=circle'));
 await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();
 await page.goto(older);
 await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toHaveValue('这里为什么要换标准？');
 await page.getByRole('button',{name:'← 暂离并保留进度',exact:true}).click();
 await expect(page.getByRole('region',{name:'当前学习安排'})).toContainText('找准比较标准');
 await page.getByRole('button',{name:'继续这次学习',exact:false}).click();
 await expect(page).toHaveURL(older);
 await page.getByRole('button',{name:'回到原题',exact:true}).click();
 await page.getByRole('button',{name:'检查一下这次理解',exact:true}).click();
 await page.getByRole('button',{name:'开始检查',exact:true}).click();
 await page.getByLabel('检查作答',{exact:true}).fill('先以小雨的12张作比较标准。');
 await page.getByRole('button',{name:'提交本次检查',exact:true}).click();
 await page.getByRole('button',{name:'回到首页',exact:true}).click();
 await expect(page.getByRole('region',{name:'当前学习安排'})).toContainText('已提交一次作答，目前尚未判定');
 await expect(page.getByRole('region',{name:'学习情况摘要'})).toContainText('未计入预写反馈和统计');
 await expect(page.getByRole('button',{name:'从这里开始讲解',exact:false})).toHaveCount(0);
});

test('missing evaluation is consistent between home, chapter status, and parent',async({page})=>{
 await page.goto(entry());await tools(page);
 await page.getByLabel('首页参考资料',{exact:true}).selectOption('none');
 await expect(page.getByRole('region',{name:'学习情况摘要'})).toContainText('还不能判断学得怎样');
 await expect(page.locator('.recent-chapter')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'从这里开始讲解',exact:false})).toHaveCount(0);
 await expect(page.getByText(/当前尚无充分评价依据/)).toBeVisible();
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'学习情况',exact:true}).click();
 await page.locator('[data-chapter=fractions]').click();
 await page.getByText('查看 6 项学习要求及状态',{exact:true}).click();
 await expect(page.getByLabel('本章要求项数').locator('b')).toHaveText(['0已达标','0需加强','6待确认']);
 await expect(page.getByText('暂无可比较的学习评价，还不能判断进步或退步。',{exact:true})).toBeVisible();
 await page.goto(entry('status','parent'));
 await expect(page.getByText(/当前尚无充分评价依据/)).toBeVisible();
 await page.goto(entry());await tools(page);
 await page.getByLabel('首页参考资料',{exact:true}).selectOption('unassessed');
 await expect(page.getByRole('region',{name:'当前学习安排'})).toContainText('已有记录尚未形成学习评价');
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('external');
 await expect(page.getByRole('region',{name:'学习情况摘要'})).toContainText('本空间暂无学习情况');
 await expect(page.getByRole('button',{name:'从这里开始讲解',exact:false})).toHaveCount(0);
});

test('time reference is shared across spaces and prompts closure without fake locking',async({page})=>{
 await page.goto(entry());await tools(page);
 await page.getByLabel('首页时间情境',{exact:true}).selectOption('26');
 await expect(page.getByRole('note')).toContainText('约 4 分钟');
 await expect(page.getByRole('button',{name:'从这里开始讲解',exact:false})).toHaveCount(0);
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('external');
 await expect(page.locator('.home-time')).toContainText('26 分钟');
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('school');
 await page.getByLabel('首页时间情境',{exact:true}).selectOption('30');
 await expect(page.getByRole('region',{name:'当前学习安排'})).toContainText('收好今天的学习');
 await expect(page.getByRole('button',{name:'从这里开始讲解',exact:false})).toHaveCount(0);
 await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toBeEnabled();
});

test('photo and text stay scoped and sent content is visible without opening chat history',async({page})=>{
 await page.goto(entry());
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jk9sAAAAASUVORK5CYII=','base64');
 await page.getByLabel('选择题目图片',{exact:true}).setInputFiles({name:'题目.png',mimeType:'image/png',buffer:png});
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('请先只给提示');
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('external');
 await expect(page.locator('.attachment-preview')).toHaveCount(0);
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('school');
 await expect(page.locator('.attachment-preview')).toContainText('题目.png');
 await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.getByRole('region',{name:'刚刚提出的问题'})).toContainText('请先只给提示');
 await expect(page.getByRole('region',{name:'刚刚提出的问题'}).getByRole('img')).toHaveCount(1);
 await expect(page.locator('.message-history')).toHaveCount(0);
 await page.reload();
 await expect(page.getByRole('region',{name:'刚刚提出的问题'})).toContainText('已保存 · 尚未处理');
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('external');
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('校外教材什么时候准备好？');
 await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.getByRole('region',{name:'刚刚提出的问题'})).toContainText('校外教材什么时候准备好？');
 await expect(page.getByRole('region',{name:'刚刚提出的问题'})).not.toContainText('请先只给提示');
});

test('long content and expanded input history occupy separate visible areas on tablet',async({page})=>{
 await page.setViewportSize({width:834,height:1112});await page.goto(entry());
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('这段内容为什么这样算？\n'.repeat(30));
 await page.getByRole('button',{name:'发送',exact:true}).click();
 await page.getByRole('button',{name:'对话历史',exact:true}).click();
 const main=await page.locator('main').boundingBox(),composer=await page.locator('.composer').boundingBox();
 expect(main!.y+main!.height).toBeLessThanOrEqual(composer!.y+1);
 await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toBeInViewport();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('existing local lessons survive the home update without new metadata',async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('deermind-structure-v1',JSON.stringify({
  version:1,studentSpace:'school',parentChild:'S0001',parentSpace:'school',
  sessions:[{id:'LIVE-legacy',learner:'S0001',space:'school',chapter:'fractions',segment:1,shown:[0,1],status:'learning',answer:'',submitted:false,endedReason:'',date:'2026-10-16'}],
  issues:[],drafts:{'student:S0001:school:LIVE-legacy':'保留原来的追问'},messages:{},access:{}
 })));
 await page.goto(entry());
 await expect(page.getByRole('region',{name:'当前学习安排'})).toContainText('具体时间未记录');
 await page.getByRole('button',{name:'继续这次学习',exact:false}).click();
 await expect(page).toHaveURL(/id=LIVE-legacy/);
 await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toHaveValue('保留原来的追问');
 await expect(page.getByRole('heading',{name:'同样相差 3 张，为什么答案不同？',exact:true})).toBeVisible();
});
