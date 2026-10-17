import { test, expect, type Page } from '@playwright/test';
async function capture(page:Page){await page.goto('/phase4.html?view=help');await page.getByText('图片、PDF、手写与语音输入',{exact:true}).click();}
async function help(page:Page){await page.goto('/phase4.html?view=help');await page.getByRole('button',{name:'载入合成题',exact:true}).click();await page.getByLabel('已有作答').fill('6×4=24');await page.getByRole('button',{name:'提交求助',exact:true}).click();}

test('同题跨页局部核对，未确认不发送，原识别与最终内容分别保留',async({page})=>{
  await capture(page);await page.getByRole('button',{name:'同题 PDF 两页',exact:true}).click();
  await page.getByRole('button',{name:'载入两页合成材料'}).click();await page.getByRole('button',{name:'查看预写识别结果'}).click();
  await page.getByLabel('确认后的输入').fill('三角形底为6厘米，对应的高为4厘米，求面积。');
  await page.getByLabel('我已核对准备发送的内容').check();
  await expect(page.getByRole('button',{name:'用于这次求助，暂不发送'})).toBeDisabled();
  await page.getByLabel('这两页属于同一道题').check();await page.reload();
  await page.getByText('图片、PDF、手写与语音输入',{exact:true}).click();
  await expect(page.getByLabel('确认后的输入')).toHaveValue('三角形底为6厘米，对应的高为4厘米，求面积。');
  await page.getByRole('button',{name:'用于这次求助，暂不发送'}).click();
  expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-phase4-product-flows-v1')!).requests.length)).toBe(0);
  await page.getByRole('button',{name:'提交求助',exact:true}).click();
  await page.getByText('查看输入来源与核对前后',{exact:true}).click();
  await expect(page.getByText(/预写识别／转写：三角形底为6厘米，对应的高为1厘米/)).toBeVisible();
  await expect(page.getByText(/正式发送：三角形底为6厘米，对应的高为4厘米/)).toBeVisible();
  await expect(page.getByText(/原始材料 2：我的原作答：6 × 4 = 24/)).toBeVisible();
});

test('语音取消不形成表现，转写可修改但不覆盖原话',async({page})=>{
  await capture(page);await page.getByRole('button',{name:'语音提问',exact:true}).click();
  await page.getByRole('button',{name:'开始录音演示（不启用麦克风）'}).click();await page.getByRole('button',{name:'取消本次录音演示'}).click();
  await page.getByRole('button',{name:'语音提问',exact:true}).click();await page.getByRole('button',{name:'开始录音演示（不启用麦克风）'}).click();await page.getByRole('button',{name:'结束并预览转写示例'}).click();
  await page.getByLabel('确认后的输入').fill('为什么三角形的面积要除以二？');await page.getByLabel('我已核对准备发送的内容').check();await page.getByRole('button',{name:'用于这次求助，暂不发送'}).click();
  await page.getByRole('button',{name:'提交求助',exact:true}).click();
  const requests=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-phase4-product-flows-v1')!).requests);
  expect(requests).toHaveLength(1);expect(requests[0].input.originals[0]).toContain('除以二');expect(requests[0].input.transcript).toContain('除以一');expect(requests[0].prompt).toContain('除以二');
  await expect(page.getByText(/未生成提示、讲解或学习判断/)).toBeVisible();
});

test('手写保存实际笔迹，刷新不丢，提交前不分析',async({page})=>{
  await capture(page);await page.getByRole('button',{name:'手写草稿',exact:true}).click();
  const pad=page.getByLabel('手写草稿板');await pad.scrollIntoViewIfNeeded();const box=(await pad.boundingBox())!;
  await page.mouse.move(box.x+20,box.y+20);await page.mouse.down();await page.mouse.move(box.x+80,box.y+60,{steps:5});await page.mouse.up();
  await expect(pad.locator('path')).toHaveCount(1);await page.reload();await page.getByText('图片、PDF、手写与语音输入',{exact:true}).click();await expect(page.getByLabel('手写草稿板').locator('path')).toHaveCount(1);
  await page.getByRole('button',{name:'保留笔迹，补充题意'}).click();await page.getByLabel('确认后的输入').fill('我的面积计算思路哪里需要检查？');await page.getByLabel('我已核对准备发送的内容').check();await page.getByRole('button',{name:'用于这次求助，暂不发送'}).click();await page.getByRole('button',{name:'提交求助',exact:true}).click();
  await page.getByText('查看输入来源与核对前后',{exact:true}).click();await expect(page.getByLabel('已提交原笔迹').locator('path')).toHaveCount(1);
});

test('跨来源记录与参考分离，资料更正不覆盖原作答，订正另留一次尝试',async({page})=>{
  await help(page);await page.getByRole('button',{name:'学习',exact:true}).click();await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();await page.getByRole('button',{name:'试着做一题'}).click();await page.getByLabel('练习作答').fill('因为两个三角形一样大');await page.getByRole('button',{name:'提交练习',exact:true}).click();
  await page.getByRole('button',{name:'题目记录',exact:true}).click();await expect(page.locator('.f-record-link')).toHaveCount(2);
  await page.getByLabel('题目来源筛选').selectOption('external');await page.locator('.f-record-link').click();
  await page.getByLabel('更正或订正方式').selectOption('transcription');await page.getByLabel('新增记录内容').fill('原稿写的是 6×4÷2=12');await page.getByLabel('新增记录说明').fill('更正先前手工录入，原稿未变化。');await page.getByRole('button',{name:'保存这次记录'}).click();
  await expect(page.getByText('6×4=24',{exact:true})).toBeVisible();await expect(page.getByText('资料更正 · 不计新作答',{exact:true})).toBeVisible();
  await page.getByLabel('更正或订正方式').selectOption('retry');await page.getByLabel('新增记录内容').fill('重新写：6×4÷2=12');await page.getByLabel('新增记录说明').fill('看过前次讲解后重新作答。');await page.getByRole('button',{name:'保存这次记录'}).click();
  await expect(page.getByText('新的订正尝试 · 尚未判定',{exact:true})).toBeVisible();
  await page.reload();await page.getByLabel('题目来源筛选').selectOption('external');await page.locator('.f-record-link').click();await expect(page.getByText('原稿写的是 6×4÷2=12',{exact:true})).toBeVisible();
  await page.getByLabel('只看确认错题').check();await expect(page.locator('.f-record-link')).toHaveCount(0);
  await page.getByLabel('记录数据来源').selectOption('reference');await expect(page.locator('.f-record-link')).toHaveCount(1);await expect(page.getByText(/预写参考只用于核对跨来源错题的表达/)).toBeVisible();
});

test('学生隐藏阻断更正副本，后台按用途打开并保留真实未执行状态',async({page})=>{
  await help(page);await page.getByRole('button',{name:'题目记录',exact:true}).click();await page.locator('.f-record-link').click();
  await page.getByLabel('新增记录内容').fill('本次订正记录');await page.getByLabel('新增记录说明').fill('已经看过讲解');await page.getByRole('button',{name:'保存这次记录'}).click();page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'删除这份外部原资料'}).click();
  await expect(page.getByText('本次订正记录',{exact:true})).toHaveCount(0);await page.reload();await expect(page.locator('.f-record-link')).toHaveCount(0);
  await page.goto('/phase4.html?role=admin&view=trace');await page.getByLabel('后台选择学习记录').selectOption({index:1});await expect(page.getByRole('button',{name:'按本次用途打开记录'})).toBeDisabled();await page.getByLabel('本次查阅用途').fill('核对已隐藏材料的订正线索');await page.getByRole('button',{name:'按本次用途打开记录'}).click();
  await expect(page.getByText(/新尝试：本次订正记录；已经看过讲解/)).toBeVisible();await expect(page.getByText(/没有可追溯的正式推断/)).toBeVisible();await expect(page.getByText(/页面已展示预写完整讲解/)).toBeVisible();
});

test('案例转领域维护绑定原事项，发布不伪装已解决历史影响',async({page})=>{
  await help(page);await page.goto('/phase4.html?role=admin&view=trace');await page.getByLabel('后台选择学习记录').selectOption({index:1});await page.getByLabel('本次查阅用途').fill('抽查三角形适用范围');await page.getByRole('button',{name:'按本次用途打开记录'}).click();
  await page.getByLabel('复核差异说明').fill('需要明确旋转后的对应高条件，先核对定义。');await page.getByRole('button',{name:'建立人工复核事项'}).click();await expect(page.getByRole('button',{name:'转入领域候选维护'})).toBeDisabled();
  await page.getByLabel('复核处理方向').selectOption('domain');await page.getByLabel('复核差异说明').fill('人工判断为领域适用范围，应准备候选核对旋转条件。');await page.getByRole('button',{name:'建立人工复核事项'}).click();await page.getByRole('button',{name:'转入领域候选维护'}).click();
  await expect(page.getByRole('heading',{name:/关联人工事项 REVIEW-/})).toBeVisible();await page.getByLabel('参数与适用条件',{exact:true}).fill('对应底高均为正且单位一致，旋转不改变对应关系。');await page.getByRole('button',{name:'检查字段与引用'}).click();await page.getByLabel('人工审核结论').selectOption('pass');await page.getByLabel('审核依据',{exact:true}).fill('人工核对三条合成案例。');await page.getByRole('button',{name:'记录批准',exact:true}).click();await page.getByRole('button',{name:'发布候选 v2'}).click();
  await page.getByRole('button',{name:'记录追溯',exact:true}).click();await expect(page.getByText(/真实采用影响与重处理仍未执行，事项未自动关闭/)).toBeVisible();
});

test('教材指定采用保留历史和范围，旧准备题单不能直接沿新版本开测',async({page})=>{
  await page.goto('/phase4.html?view=course');await page.getByRole('button',{name:'创建演示空间',exact:true}).click();await page.getByRole('button',{name:'查看本次检测安排'}).click();await page.getByRole('button',{name:'开始本次检测',exact:true}).click();await page.getByLabel('范围检测作答').fill('原版本下的作答');await page.getByRole('button',{name:'提交这一题'}).click();await page.getByRole('button',{name:'结束并保留已完成部分'}).click();await page.getByRole('button',{name:'另选范围，准备新的检测'}).click();await page.getByRole('button',{name:'查看本次检测安排'}).click();
  await page.goto('/phase4.html?role=admin&view=materials');await page.getByRole('button',{name:'载入合成材料任务'}).click();await page.getByRole('button',{name:'载入该任务的识别示例'}).click();await page.getByLabel('第1页识别文本').fill('底为6厘米，对应高4厘米。');await page.getByLabel('已核对第 1 页原材料').check();await page.getByLabel('已核对第 2 页原材料').check();await page.getByLabel('已核对章节、目标及引用对象的适用关系').check();await page.getByLabel('已核对自编参考，并保留非原书答案的来源说明').check();await page.getByLabel('教材审核依据').fill('已核对合成内容和参考。');await page.getByRole('button',{name:'批准当前教材候选'}).click();await page.getByRole('button',{name:'发布合成教材 v2'}).click();
  await page.getByLabel(/我的面积学习 · 当前 v1 · 原章节/).check();await expect(page.getByRole('button',{name:'指定这些课程采用教材 v2'})).toBeDisabled();await page.getByLabel('课程采用依据').fill('保持原章节范围，旧检测只保留当时结果。');await page.getByLabel('已核对所选空间、目标变更与保留范围').check();await page.getByRole('button',{name:'指定这些课程采用教材 v2'}).click();
  await page.goto('/phase4.html?view=course');await expect(page.getByRole('button',{name:'开始本次检测',exact:true})).toBeDisabled();await expect(page.getByText(/采用版本已变化，请返回重新准备安排/)).toBeVisible();await page.getByRole('button',{name:'返回调整范围'}).click();await page.getByText('查看本空间之前的检测',{exact:true}).click();await expect(page.getByText('原版本下的作答',{exact:true})).toBeVisible();
  const state=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-phase4-course-setup-v1')!));expect(state.courses[0].version).toBe(2);expect(state.examHistory[0].version).toBe(1);expect(state.courses[0].units).toEqual(state.adoptions[0].scope);
});

test('新增输入、记录和追溯页面在平板手机宽度不溢出',async({page},testInfo)=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await help(page);
  for(const view of ['help','records','trace']){
    await page.goto(`/phase4.html?role=${view==='trace'?'admin':'student'}&view=${view}`);
    if(view==='help'){await page.getByText('图片、PDF、手写与语音输入',{exact:true}).click();await page.getByRole('button',{name:'载入两页合成材料'}).click();await page.getByRole('button',{name:'查看预写识别结果'}).click();}
    if(view==='records')await page.locator('.f-record-link').click();
    if(view==='trace'){await page.getByLabel('后台选择学习记录').selectOption({index:1});await page.getByLabel('本次查阅用途').fill('布局走查');await page.getByRole('button',{name:'按本次用途打开记录'}).click();}
    for(const width of [1280,834,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect(await page.locator('.f-flow-page').evaluate(e=>e.scrollWidth<=e.clientWidth)).toBe(true);await page.screenshot({path:testInfo.outputPath(`${view}-${width}.png`),fullPage:true});}
  }expect(errors).toEqual([]);
});
