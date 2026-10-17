import { test, expect } from '@playwright/test';

test('无作答可只求提示，完整解答按明确操作展开，未判题不进错题', async ({page}) => {
  await page.goto('/phase4.html?view=help');
  await page.getByRole('button',{name:'载入合成题',exact:true}).click();
  await page.getByLabel('只给提示',{exact:true}).check();
  await page.getByRole('button',{name:'提交求助',exact:true}).click();
  await expect(page.getByRole('heading',{name:'先给一个提示',exact:false})).toBeVisible();
  await expect(page.locator('.f-followup')).not.toContainText('12 平方米');
  await expect(page.getByText('未作答',{exact:true}).first()).toBeVisible();
  await page.getByRole('button',{name:'现在给我完整讲解'}).click();
  await expect(page.locator('.f-followup')).toContainText('12 平方米');
  await page.getByLabel('只看确认错题').check();
  await expect(page.getByText(/暂无确认错题/)).toBeVisible();
});

test('更改示例题后不套用预写解答，草稿刷新保存，删除不恢复学生条目', async ({page}) => {
  await page.goto('/phase4.html?view=help');
  await page.getByRole('button',{name:'载入合成题',exact:true}).click();
  await page.getByRole('textbox',{name:'求助题目',exact:true}).fill('一个新的自由输入问题');
  await page.reload();
  await expect(page.getByRole('textbox',{name:'求助题目',exact:true})).toHaveValue('一个新的自由输入问题');
  await page.getByRole('button',{name:'提交求助',exact:true}).click();
  await expect(page.getByText('已保存请求。原型尚未连接模型，未生成提示、讲解或学习判断。')).toBeVisible();
  page.once('dialog',d=>d.accept());
  await page.getByRole('button',{name:'删除这条原始资料'}).click();
  await page.getByRole('button',{name:'题目记录',exact:true}).click();
  await expect(page.getByText('一个新的自由输入问题',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'家长',exact:true}).click();
  await page.getByRole('button',{name:'学习情况',exact:true}).click();
  await page.getByText('查看本轮求助原资料',{exact:true}).click();
  await expect(page.getByText('一个新的自由输入问题',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'删除这条原始资料'})).toHaveCount(0);
});

test('章节状态与日期统计分离，展开依据，不跨空间借数据', async ({page}) => {
  await page.goto('/phase4.html?view=status');
  const before=await page.getByLabel('当前学习要求项数').innerText();
  await expect(page.getByTestId('answer-stat')).toContainText('3 次，正确 2 次 · 67%');
  await page.getByLabel('作答统计时间范围').selectOption('30');
  await expect(page.getByTestId('answer-stat')).toContainText('4 次，正确 3 次 · 75%');
  await page.getByLabel('作答统计时间范围').selectOption('all');
  await expect(page.getByTestId('answer-stat')).toContainText('5 次，正确 3 次 · 60%');
  expect(await page.getByLabel('当前学习要求项数').innerText()).toBe(before);
  await page.getByRole('button',{name:'展开具体要求'}).click();
  await page.getByRole('button',{name:/解释面积公式为什么要除以 2/}).click();
  await expect(page.locator('.f-evidence')).toContainText('假定评价认为尚未达到解释要求');
  await page.getByLabel('查看课程空间').selectOption('external');
  await expect(page.getByRole('heading',{name:'校外内容还没有准备好'})).toBeVisible();
  await expect(page.getByLabel('当前学习要求项数')).toHaveCount(0);
  await expect(page.getByTestId('answer-stat')).toHaveCount(0);
});

test('系统故障与失效不算孩子待确认，家长咨询不进入学生视图', async ({page}) => {
  await page.goto('/phase4.html?role=parent&view=status');
  await page.getByText('走查异常状态',{exact:true}).click();
  await page.getByLabel('评价读取状态').selectOption('failed');
  await expect(page.getByRole('heading',{name:'学习情况暂时无法读取'})).toBeVisible();
  await expect(page.getByLabel('当前学习要求项数')).toHaveCount(0);
  await page.getByLabel('评价读取状态').selectOption('stale');
  await expect(page.getByRole('heading',{name:'相关判断正在更新'})).toBeVisible();
  await page.getByLabel('咨询孩子的学习情况').fill('家长的私人问题');
  await page.getByRole('button',{name:'发送',exact:true}).click();
  await expect(page.getByText('家长的私人问题',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'学生',exact:true}).click();
  await page.getByRole('button',{name:'学习情况',exact:true}).click();
  await page.getByRole('button',{name:'对话历史',exact:true}).click();
  await expect(page.getByText('家长的私人问题',{exact:true})).toHaveCount(0);
});

test('维护不能跳过检查与审核，修改后批准失效，发布与采用分开', async ({page}) => {
  await page.goto('/phase4.html?role=admin&view=maintenance');
  const publish=page.getByRole('button',{name:'发布候选 v2',exact:true});
  await expect(publish).toBeDisabled();
  await page.getByRole('textbox',{name:'参数与适用条件',exact:true}).fill('底和对应高为正数、单位一致；允许旋转摆放，但不得把斜边当高。');
  await page.getByRole('button',{name:'检查字段与引用'}).click();
  await page.getByLabel('人工审核结论').selectOption('unresolved');
  await page.getByRole('textbox',{name:'审核依据',exact:true}).fill('核对三条代表性案例及对应高条件；当前仅为演示人工审核。');
  await expect(page.getByRole('button',{name:'记录批准'})).toBeDisabled();
  await page.getByLabel('人工审核结论').selectOption('pass');
  await page.getByRole('button',{name:'记录批准'}).click();
  await expect(publish).toBeEnabled();
  await page.getByRole('textbox',{name:'名称',exact:true}).fill('旋转摆放的三角形面积计算');
  await expect(publish).toBeDisabled();
  await page.getByRole('button',{name:'检查字段与引用'}).click();
  await page.getByRole('button',{name:'记录批准'}).click();
  await publish.click();
  await expect(page.getByText('目录 v2 · 校内空间 v1',{exact:true})).toBeVisible();
  await page.reload();
  await expect(page.getByText('目录 v2 · 校内空间 v1',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'指定所选空间采用 v2'})).toBeDisabled();
  await page.getByLabel(/校内合成演示空间 · 当前 v1/).check();
  await page.getByRole('button',{name:'指定所选空间采用 v2'}).click();
  await expect(page.getByText('目录 v2 · 校内空间 v2',{exact:true})).toBeVisible();
  await expect(page.getByText(/真实失效、待执行／失败／未决重处理尚未接入/)).toBeVisible();
});

test('非法引用与基础变化不允许沿旧检查发布', async ({page}) => {
  await page.goto('/phase4.html?role=admin&view=maintenance');
  await page.getByRole('textbox',{name:'方法引用',exact:true}).fill('MISSING@1');
  await page.getByRole('button',{name:'检查字段与引用'}).click();
  await expect(page.getByRole('status')).toContainText('检查未通过');
  await page.getByRole('textbox',{name:'方法引用',exact:true}).fill('ST-DEMO-AREA@1');
  await page.getByRole('textbox',{name:'名称',exact:true}).fill('三角形面积（明确边界）');
  await page.getByRole('button',{name:'检查字段与引用'}).click();
  await page.getByLabel('人工审核结论').selectOption('pass');
  await page.getByRole('textbox',{name:'审核依据',exact:true}).fill('已人工核对适用范围。');
  await page.getByRole('button',{name:'记录批准'}).click();
  await page.getByText('走查引用变化',{exact:true}).click();
  await page.getByLabel('模拟引用基础已经变化').check();
  await expect(page.getByRole('button',{name:'发布候选 v2',exact:true})).toBeDisabled();
});

test('检测暂停后仍不能直接切入其他教学，家长初次查看不产生展示记录', async ({page}) => {
  await page.goto('/phase4.html?role=parent');
  await expect(page.getByText(/已展示 0 段/)).toBeVisible();
  await page.getByRole('button',{name:'学生',exact:true}).click();
  await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();
  await page.getByRole('button',{name:'继续下一段'}).click();
  await page.getByRole('button',{name:'继续下一段'}).click();
  await page.getByRole('button',{name:'做一次结束检查'}).click();
  await page.getByRole('button',{name:'开始检查',exact:true}).click();
  await page.getByRole('button',{name:'暂时离开'}).click();
  await expect(page.getByRole('button',{name:'学习',exact:true})).toBeDisabled();
  await page.goto('/phase4.html?role=student&view=help');
  await expect(page.getByRole('textbox',{name:'求助题目',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'继续未结束的检测'}).click();
  await expect(page.getByRole('textbox',{name:'检测作答',exact:true})).toBeVisible();
});

test('新增流程适配平板与手机，留存当前截图', async ({page},testInfo) => {
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  for(const view of ['help','status','maintenance']){
    await page.goto(`/phase4.html?role=${view==='maintenance'?'admin':'student'}&view=${view}`);
    for(const width of [1280,834,390]){
      await page.setViewportSize({width,height:900});
      await expect(page.locator('.f-flow-page')).toBeVisible();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      expect(await page.locator('.f-flow-page').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
      if(view==='status'){
        await expect(page.getByLabel('当前学习要求项数')).toBeInViewport();
        await expect(page.getByLabel('对学习情况有疑问，直接说说')).toBeInViewport();
        const bounds=await page.evaluate(()=>({main:document.querySelector('.f-flow-page')!.getBoundingClientRect().bottom,composer:document.querySelector('.f-inline-composer')!.getBoundingClientRect().top}));
        expect(bounds.main).toBeLessThanOrEqual(bounds.composer+1);
      }
      await page.screenshot({path:testInfo.outputPath(`${view}-${width}.png`),fullPage:true});
    }
  }
  expect(errors).toEqual([]);
});
