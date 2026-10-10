import { test, expect, type Page } from '@playwright/test';

async function go(page: Page, path: string) {
  await page.goto(`/#/${path}`);
}
async function scenario(page: Page, value: string) {
  if (!(await page.getByText('演示状态', { exact: false }).isVisible()))
    await page.getByRole('button', { name: '走查工具' }).click();
  await page.locator('.review-tools select').selectOption(value);
}
async function eraseExam(page: Page) {
  await go(page, 'student/materials');
  await page.getByRole('button', { name: '删除整份试卷', exact: true }).click();
  await page.getByRole('button', { name: '确认删除整卷', exact: true }).click();
  await expect(page.getByRole('heading', { name: '这份资料已从你的界面移除' })).toBeVisible();
}

test('整卷归集、提示与完整讲解分别呈现，练习输入按题保留', async ({ page }) => {
  await go(page, 'student/upload');
  await page.getByRole('button', { name: '使用示例试卷继续' }).click();
  await expect(page.getByText('3 道示例题 · 2 道确认错题')).toBeVisible();
  await page.getByRole('button', { name: /确认错题 2/ }).click();
  await expect(page.locator('.question-row')).toHaveCount(2);
  await page.locator('.question-row').filter({ hasText: '八折' }).click();
  await page.getByLabel('写下现在的思路').fill('先确定哪个量是整体');
  await page.getByRole('button', { name: '只给提示', exact: true }).click();
  await expect(page.locator('.hint-text')).toContainText('80%');
  await expect(page.locator('.explanation-card')).not.toContainText('200');
  await page.getByRole('button', { name: '看完整讲解' }).click();
  await expect(page.locator('.explanation-steps')).toContainText('200');
  await go(page, 'student/materials');
  await page.locator('.question-row').filter({ hasText: '计算：' }).click();
  await expect(page.getByLabel('写下现在的思路')).toHaveValue('');
});

test('自测遵守章节范围，求助结束检测并保留草稿和未检测部分', async ({ page }) => {
  await go(page, 'student/test');
  await page.getByLabel('百分数的应用', { exact: true }).check();
  await page.getByRole('button', { name: '开始本次自测' }).click();
  await expect(page.locator('.problem-text')).toContainText('25%');
  await page.getByLabel('我的作答').fill('我认为是四分之一');
  await page.getByRole('button', { name: '提交，进入下一题' }).click();
  await expect(page.locator('.problem-text')).toContainText('八折');
  await expect(page.getByText('前 1 题已收到，尚未展示对错。')).toBeVisible();
  await page.getByLabel('我的作答').fill('这里我不确定整体');
  await page.getByRole('button', { name: '结束检测并求讲解' }).click();
  await page.getByRole('button', { name: '结束并讲解', exact: true }).click();
  await expect(page.locator('.explanation-steps')).toContainText('200');
  await expect(page.locator('.original-work')).toContainText('这里我不确定整体');
  await go(page, 'student/results');
  await expect(page.getByText('中途请求讲解，未做的部分仍是未检测。')).toBeVisible();
  await expect(page.locator('.result-answer')).toHaveCount(1);
  await expect(page.locator('.result-stats')).toContainText('待核验');
  await expect(page.getByText('未提交草稿：这里我不确定整体')).toBeVisible();
});

test('删除后家长可提报相关依据，后台纠错不恢复学生条目或旧链接', async ({ page }) => {
  await go(page, 'student/home');
  await eraseExam(page);
  await go(page, 'parent/overview');
  await page.getByRole('button', { name: '查看相关依据' }).click();
  await expect(page.getByRole('dialog')).toContainText('不能恢复或修改');
  await page.getByRole('button', { name: '提报已删资料的识别问题' }).click();
  await go(page, 'admin/issues');
  await page.getByRole('button', { name: '记录开始复核' }).click();
  await page.getByRole('button', { name: '确认依据并执行示例修复' }).click();
  await go(page, 'parent/notices');
  await expect(page.getByRole('heading', { name: '第 2 题的识别结果已更新' })).toBeVisible();
  await go(page, 'student/materials');
  await expect(page.getByRole('heading', { name: '这份资料已从你的界面移除' })).toBeVisible();
  await go(page, 'student/question');
  await expect(page.getByRole('heading', { name: '当前材料不可查看' })).toBeVisible();
  await expect(page.locator('.original-work')).toHaveCount(0);
});

test('局部未确认不归入错题；校外空间不带入校内资料、咨询或草稿', async ({ page }) => {
  await go(page, 'student/upload');
  await scenario(page, 'partial');
  await page.getByRole('button', { name: '使用示例试卷继续' }).click();
  await expect(page.getByText('3 道示例题 · 1 道确认错题 · 1 道待确认')).toBeVisible();
  await page.getByRole('button', { name: /确认错题 1/ }).click();
  await expect(page.locator('.question-row')).toHaveCount(1);
  await go(page, 'parent/consult');
  await page.getByLabel('咨询问题').fill('校内的私人咨询草稿');
  await page.getByLabel('当前课程空间').selectOption('extension');
  await go(page, 'parent/consult');
  await expect(page.getByLabel('咨询问题')).toHaveValue('');
  await expect(page.locator('.bubble')).toHaveCount(0);
  await go(page, 'student/materials');
  await expect(page.getByRole('heading', { name: '这里还没有学习资料' })).toBeVisible();
  await page.getByLabel('当前课程空间').selectOption('school');
  await go(page, 'student/materials');
  await expect(page.getByText('3 道示例题 · 1 道确认错题 · 1 道待确认')).toBeVisible();
});

test('首次确认按家长、孩子顺序完成；解绑立即阻止家长再次查看', async ({ page }) => {
  await go(page, 'student/home');
  await page.getByRole('button', { name: '走查工具' }).click();
  await page.getByRole('button', { name: '首次使用场景' }).click();
  await expect(page.getByRole('button', { name: '我了解了，愿意开始' })).toBeDisabled();
  await go(page, 'parent/settings');
  await page.getByLabel('我已了解上述演示数据说明').check();
  await page.getByRole('button', { name: '确认首次说明' }).click();
  await go(page, 'parent/overview');
  await expect(page.getByRole('heading', { name: '首次使用确认尚未完成' })).toBeVisible();
  await go(page, 'student/home');
  await page.getByRole('button', { name: '我了解了，愿意开始' }).click();
  await expect(page.getByRole('heading', { name: '今天，想弄懂什么？' })).toBeVisible();
  await go(page, 'admin/accounts');
  await page.getByRole('button', { name: '解除关联', exact: true }).click();
  await page.getByRole('dialog').getByRole('checkbox').check();
  await page.getByRole('button', { name: '确认并记录' }).click();
  await go(page, 'parent/overview');
  await expect(page.getByRole('heading', { name: '当前没有可查看的孩子' })).toBeVisible();
});

test('单独错题仅显示该题相关依据，不借用整卷正确题', async ({ page }) => {
  await go(page, 'student/upload');
  await page.getByRole('button', { name: '独立错题', exact: true }).click();
  await page.getByRole('button', { name: '使用独立题示例继续' }).click();
  await expect(page.getByText('1 道示例题 · 1 道确认错题')).toBeVisible();
  await go(page, 'parent/overview');
  await page.getByRole('button', { name: '查看相关依据' }).click();
  await expect(page.getByRole('dialog')).toContainText('八折');
  await expect(page.getByRole('dialog')).not.toContainText('25%');
});

test('领域候选批准不等于启用，基础冲突后必须重新检查批准', async ({ page }) => {
  await go(page, 'admin/domain');
  await page.getByRole('button', { name: '发起基础领域维护' }).click();
  await page.getByRole('button', { name: '查看示例检查结果' }).click();
  await page.getByRole('button', { name: '审核候选' }).click();
  await page.getByRole('dialog').getByRole('checkbox').check();
  await page.getByRole('button', { name: '批准此候选，进入待提交' }).click();
  await expect(page.getByText('已批准，待提交启用 · v1')).toBeVisible();
  await page.getByRole('button', { name: '演示基础冲突' }).click();
  await expect(page.getByRole('button', { name: '基础冲突，暂不能启用' })).toBeDisabled();
  await page.getByRole('button', { name: '重取基础，重新检查' }).click();
  await page.getByRole('button', { name: '查看示例检查结果' }).click();
  await page.getByRole('button', { name: '审核候选' }).click();
  await page.getByRole('dialog').getByRole('checkbox').check();
  await page.getByRole('button', { name: '批准此候选，进入待提交' }).click();
  await page.getByRole('button', { name: '提交并启用此版本' }).click();
  await expect(page.getByText('新版本已启用 · v2')).toBeVisible();
  await page.getByLabel('当前课程空间').selectOption('extension');
  await go(page, 'admin/domain');
  await expect(page.getByText('当前版本 · v1')).toBeVisible();
});

test('处理中刷新转为可恢复任务；重试不改变独立题类型', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-10-09T00:00:00Z') });
  await page.clock.pauseAt(new Date('2026-10-09T00:00:01Z'));
  await go(page, 'student/upload');
  await page.getByRole('button', { name: '独立错题', exact: true }).click();
  await page.getByRole('button', { name: '使用独立题示例继续' }).click();
  await expect(page.getByRole('heading', { name: '正在整理题目与作答' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '这次处理没有完成' })).toBeVisible();
  await page.clock.resume();
  await page.getByRole('button', { name: '重试原任务', exact: true }).click();
  await expect(page.getByText('1 道示例题 · 1 道确认错题')).toBeVisible();
  await expect(page.getByRole('button', { name: '删除独立题', exact: true })).toBeVisible();
});

test('断网不吞作答，不展示新帮助；恢复后可以原位提交', async ({ page }) => {
  await go(page, 'student/test');
  await page.getByLabel('分数除法', { exact: true }).check();
  await page.getByRole('button', { name: '开始本次自测' }).click();
  await page.getByLabel('我的作答').fill('保留这份草稿');
  await scenario(page, 'offline');
  await page.getByRole('button', { name: '提交并结束' }).click();
  await expect(page.getByLabel('我的作答')).toHaveValue('保留这份草稿');
  await page.reload();
  await expect(page.getByLabel('我的作答')).toHaveValue('保留这份草稿');
  await scenario(page, 'normal');
  await page.getByRole('button', { name: '提交并结束' }).click();
  await expect(page.locator('.result-answer')).toContainText('保留这份草稿');
});

test('受控规则交付独立于领域模型，检查失败不能启用', async ({ page }) => {
  await go(page, 'admin/domain');
  await page.getByRole('button', { name: '其他语义模型交付' }).click();
  await page.getByRole('button', { name: '接收示例交付包' }).click();
  await page.getByRole('button', { name: '模拟检查未通过' }).click();
  await expect(page.getByRole('button', { name: '交付并限定启用' })).toHaveCount(0);
  await page.getByRole('button', { name: '接收示例交付包' }).click();
  await page.getByRole('button', { name: '查看合成检查结果' }).click();
  await page.getByRole('button', { name: '批准此版本及范围' }).click();
  await page.getByRole('button', { name: '交付并限定启用' }).click();
  await expect(page.getByRole('dialog')).toContainText('已限定启用');
  await expect(page.getByText('当前版本 · v1')).toBeVisible();
});

test('家长删除咨询后独立事项保留，新会话不带回原内容', async ({ page }) => {
  await go(page, 'student/home');
  await eraseExam(page);
  await go(page, 'parent/overview');
  await page.getByRole('button', { name: '查看相关依据' }).click();
  await page.getByRole('button', { name: '提报已删资料的识别问题' }).click();
  await go(page, 'parent/consult');
  await page.getByLabel('咨询问题').fill('这段私人咨询需要删除');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await page.getByRole('button', { name: '删除整段会话', exact: true }).click();
  await page.getByRole('button', { name: '确认删除会话' }).click();
  await page.getByRole('button', { name: '这条判断有哪些依据？' }).click();
  await expect(page.locator('.conversation')).not.toContainText('这段私人咨询需要删除');
  await go(page, 'parent/notices');
  await expect(page.getByText('已提交，待复核')).toBeVisible();
});

test('用时跨空间累计，30 分钟提醒不锁定；章节讲解对应所点章节', async ({ page }) => {
  await go(page, 'student/home');
  await page.getByRole('button', { name: '12 / 30 分钟' }).click();
  await page.getByLabel('补记分钟数').fill('18');
  await page.getByRole('button', { name: '确认补记' }).click();
  await expect(page.getByText(/今天已记录 30 分钟。先保存进度/)).toBeVisible();
  await page.getByLabel('当前课程空间').selectOption('extension');
  await expect(page.getByRole('button', { name: '30 / 30 分钟' })).toBeVisible();
  await expect(page.getByRole('button', { name: '拍题 / 上传资料' })).toBeEnabled();
  await page.getByLabel('当前课程空间').selectOption('school');
  await go(page, 'student/book');
  await page
    .locator('.chapter-row')
    .filter({ hasText: '分数除法' })
    .getByRole('button', { name: '打开章节' })
    .click();
  await expect(page.locator('.lesson-content')).toContainText('3/4 除以 1/2');
  await expect(page.locator('.lesson-content')).not.toContainText('百分数表示');
});

for (const [role, path, width, height] of [
  ['student', 'student/home', 1280, 800],
  ['parent', 'parent/overview', 390, 844],
  ['admin', 'admin/domain', 1440, 960],
] as const) {
  test(`${role} 布局无页面横向溢出及运行错误`, async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width, height });
    await go(page, path);
    await expect(page.locator('h1')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
      true,
    );
    expect(errors).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`${role}.png`), fullPage: true });
  });
}
