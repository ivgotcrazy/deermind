import { test, expect, type Page } from '@playwright/test';

async function createCourse(page:Page, composite=false){
  await page.goto('/phase4.html?view=course');
  if(composite)await page.getByLabel(/2.1 分割与面积关系/).check();
  await page.getByRole('button',{name:'创建演示空间',exact:true}).click();
}
async function identityCheck(page:Page){
  await page.getByLabel('已在系统外核实本人及本次操作所需关系').check();
  await page.getByLabel('身份核实依据').fill('合成身份与关系已人工核对，仅用于走查。');
}

test('范围决定题量，未准备章节不伪装已覆盖，真实教材不能假装发布',async({page})=>{
  await page.goto('/phase4.html?view=course');
  await page.getByLabel('选用教材').selectOption('school');
  await expect(page.getByRole('button',{name:'创建演示空间',exact:true})).toBeDisabled();
  await page.getByLabel('选用教材').selectOption('demo');
  await page.getByLabel(/2.1 分割与面积关系/).check();
  await page.getByRole('button',{name:'创建演示空间',exact:true}).click();
  await page.getByRole('button',{name:'查看本次检测安排'}).click();
  await expect(page.getByText('3 题 · 参考 8 分钟',{exact:true})).toBeVisible();
  await expect(page.getByText(/你选择的范围有 1 节尚不能正式检测/)).toBeVisible();
  await page.getByRole('button',{name:'返回调整范围'}).click();
  await page.getByLabel(/1.1 根据底和高计算/).uncheck();
  await page.getByLabel(/2.1 分割与面积关系/).uncheck();
  await page.getByRole('button',{name:'查看本次检测安排'}).click();
  await expect(page.getByText('1 题 · 参考 3 分钟',{exact:true})).toBeVisible();
  await expect(page.getByRole('textbox',{name:'范围检测作答'})).toHaveCount(0);
});

test('范围检测暂离恢复且禁止绕入教学，求助结束，另开后保留历史',async({page})=>{
  await createCourse(page);
  await page.getByRole('button',{name:'查看本次检测安排'}).click();
  await page.getByRole('button',{name:'开始本次检测',exact:true}).click();
  await page.getByLabel('范围检测作答').fill('8×5÷2=20');
  await page.getByRole('button',{name:'提交这一题'}).click();
  await expect(page.getByText('20 平方厘米。',{exact:true})).toHaveCount(0);
  await page.getByLabel('范围检测作答').fill('第二题的未提交想法');
  await page.getByRole('button',{name:'暂离本次检测'}).click();
  await page.goto('/phase4.html?view=help');
  await expect(page.getByRole('heading',{name:'这次检测还没有结束'})).toBeVisible();
  await expect(page.getByRole('button',{name:'学习',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'返回本次检测'}).click();
  await expect(page.getByLabel('范围检测作答')).toHaveValue('第二题的未提交想法');
  await page.getByRole('button',{name:'需要帮助，结束本次检测'}).click();
  await expect(page.getByRole('heading',{name:'本次检测已结束'})).toBeVisible();
  await expect(page.getByText('旋转只改变摆放方向。先找题目给定的一组底和对应的垂直高。',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'另选范围，准备新的检测'}).click();
  await page.reload();
  await page.getByText('查看本空间之前的检测',{exact:true}).click();
  await expect(page.getByText('8×5÷2=20',{exact:true})).toBeVisible();
  await expect(page.getByText(/已提交 1 \/ 3 题，结束原因：请求帮助/)).toBeVisible();
});

test('接受建议仅准备，依据变化禁止旧安排开测，拒绝不修改学习判断',async({page})=>{
  await createCourse(page);
  await page.getByRole('button',{name:'先看看建议的检测安排'}).click();
  await expect(page.getByText('1 题 · 参考 3 分钟',{exact:true})).toBeVisible();
  await expect(page.getByLabel('范围检测作答')).toHaveCount(0);
  await page.getByText('走查建议依据变化',{exact:true}).click();
  await page.getByLabel('建议依据状态').selectOption('stale');
  await expect(page.getByRole('button',{name:'开始本次检测',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'返回调整范围'}).click();
  await page.getByRole('button',{name:'仅重置本条演示选择'}).click();
  await page.getByRole('button',{name:'不接受这条建议'}).click();
  await expect(page.getByText(/已记录选择：不接受，不改变能力判断/)).toBeVisible();
  await expect(page.getByLabel('范围检测作答')).toHaveCount(0);
});

test('教材同任务核对、审核随编辑失效，新发布只供新空间选用',async({page})=>{
  await createCourse(page);
  await page.goto('/phase4.html?role=admin&view=materials');
  await page.getByRole('button',{name:'载入合成材料任务'}).click();
  const task=await page.getByTestId('import-task').innerText();
  await page.reload();
  await expect(page.getByTestId('import-task')).toHaveText(task);
  await page.getByRole('button',{name:'载入该任务的识别示例'}).click();
  await page.getByLabel('第1页识别文本').fill('两个全等三角形拼成平行四边形。三角形底为6厘米，对应高为4厘米。请计算面积。');
  await page.getByLabel('已核对第 1 页原材料').check();
  await page.getByLabel('已核对章节、目标及引用对象的适用关系').check();
  await page.getByLabel('已核对自编参考，并保留非原书答案的来源说明').check();
  await page.getByLabel('教材审核依据').fill('已核对两页原文、引用对象、参考与可用范围。');
  await expect(page.getByRole('button',{name:'批准当前教材候选'})).toBeDisabled();
  await page.getByLabel('已核对第 2 页原材料').check();
  await page.getByRole('button',{name:'批准当前教材候选'}).click();
  await expect(page.getByRole('button',{name:'发布合成教材 v2'})).toBeEnabled();
  await page.getByLabel('教材目标标准').fill('在对应底、高给定且单位一致时独立计算，解释为什么除以2；组合图形不纳入本次评价。');
  await expect(page.getByRole('button',{name:'发布合成教材 v2'})).toBeDisabled();
  await expect(page.getByRole('button',{name:'批准当前教材候选'})).toBeDisabled();
  await page.getByLabel('已核对章节、目标及引用对象的适用关系').check();
  await page.getByRole('button',{name:'批准当前教材候选'}).click();
  await page.getByRole('button',{name:'发布合成教材 v2'}).click();
  await page.goto('/phase4.html?view=course');
  await expect(page.getByLabel('当前演示空间')).toContainText('教材与目标 v1');
  await page.getByRole('button',{name:'创建另一个空间'}).click();
  await expect(page.getByLabel('选用教材')).toContainText('v2');
  await page.getByLabel('空间名称').fill('采用新版的空间');
  await page.getByRole('button',{name:'创建演示空间',exact:true}).click();
  const courses=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-phase4-course-setup-v1')!).courses);
  expect(courses.map((c:any)=>c.version)).toEqual([1,2]);
});

test('身份操作需核实，找回不另建档案，解除单条关联后家长旧链接失效',async({page})=>{
  await createCourse(page);
  await page.goto('/phase4.html?role=admin&view=accounts');
  await expect(page.getByRole('button',{name:'记录原账号找回'})).toBeDisabled();
  await identityCheck(page);
  await page.getByRole('button',{name:'记录原账号找回'}).click();
  await expect(page.getByText('演示学生 · 学生 · CHILD-DEMO-1 · 凭据记录 v2',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'解除所选关联'})).toBeDisabled();
  await identityCheck(page);
  page.once('dialog',d=>d.accept());
  await page.getByRole('button',{name:'解除所选关联'}).click();
  await expect(page.getByText('PARENT-DEMO-2 → CHILD-DEMO-1：有效',{exact:true})).toBeVisible();
  await page.goto('/phase4.html?role=parent&view=status');
  await expect(page.getByRole('heading',{name:'当前没有可查看的学生关联'})).toBeVisible();
  await expect(page.getByLabel('当前学习要求项数')).toHaveCount(0);
  const state=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-phase4-course-setup-v1')!));
  expect(state.accounts.profiles).toHaveLength(3);expect(state.courses).toHaveLength(1);
  await page.goto('/phase4.html?view=course');
  await expect(page.getByLabel('当前演示空间')).toBeVisible();
  await page.goto('/phase4.html?role=admin&view=accounts');
  await page.getByLabel('演示账号名称').fill('新增合成家长');
  await expect(page.getByRole('button',{name:'创建合成账号档案'})).toBeDisabled();
  await identityCheck(page);
  await page.getByRole('button',{name:'创建合成账号档案'}).click();
  expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-phase4-course-setup-v1')!).accounts.profiles.length)).toBe(4);
  await identityCheck(page);await page.getByRole('button',{name:'建立所选关联'}).click();
  await page.goto('/phase4.html?role=parent&view=status');
  await expect(page.getByLabel('当前学习要求项数')).toBeVisible();
});

test('家长与孩子分别确认，未完成不能进入新的学习',async({page})=>{
  await page.goto('/phase4.html?role=parent&view=accounts');
  await page.getByText('走查首次使用前的状态',{exact:true}).click();
  await page.getByRole('button',{name:'重置双方演示确认'}).click();
  await page.getByRole('button',{name:'完成家长端演示确认'}).click();
  await page.goto('/phase4.html?view=course');
  await expect(page.getByRole('heading',{name:'先完成必要的首次说明'})).toBeVisible();
  await page.getByRole('button',{name:'查看账号与首次说明'}).click();
  await page.getByRole('button',{name:'我愿意参加这次演示'}).click();
  await page.getByRole('button',{name:'教材与检测',exact:true}).click();
  await expect(page.getByRole('button',{name:'创建演示空间',exact:true})).toBeEnabled();
});

test('课程、教材和账号在三种宽度可操作，无水平溢出',async({page},testInfo)=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  for(const view of ['course','materials','accounts']){
    await page.goto(`/phase4.html?role=${view==='course'?'student':'admin'}&view=${view}`);
    for(const width of [1280,834,390]){
      await page.setViewportSize({width,height:900});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      expect(await page.locator('.f-flow-page').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
      await page.screenshot({path:testInfo.outputPath(`${view}-${width}.png`),fullPage:true});
    }
  }
  expect(errors).toEqual([]);
});
