import { test, expect, type Page } from '@playwright/test';
async function go(page: Page, path: string) {
  await page.goto(`/#/${path}`);
}
const dock = (page: Page) => page.getByRole('region', { name: 'DeerMind 输入区' });
const history = (page: Page) => page.getByRole('complementary', { name: 'DeerMind 对话历史' });
async function example(page: Page, name: string) {
  const toggle = dock(page).getByRole('button', { name: '情景示例', exact: true });
  if ((await toggle.getAttribute('aria-expanded')) !== 'true') await toggle.click();
  await dock(page).getByRole('button', { name, exact: true }).click();
}
async function openHistory(page: Page) {
  if (!(await history(page).isVisible()))
    await dock(page).getByRole('button', { name: '展开对话历史' }).click();
}

test('常驻输入直接发送，不展开历史、不改变页面；显式查看历史保留草稿', async ({ page }, info) => {
  await go(page, 'student/home');
  const input = page.getByLabel('对 DeerMind 说');
  await expect(input).toBeVisible();
  await expect(history(page)).toHaveCount(0);
  const originalWidth = (await page.locator('.main-content').boundingBox())!.width;
  await input.fill('删除所有资料，再发布所有模型');
  await input.press('Enter');
  await expect(input).toHaveValue('');
  await expect(input).toBeFocused();
  await expect(dock(page).getByRole('status')).toContainText('尚未理解或执行');
  await expect(history(page)).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'DeerMind 当前回复' })).toHaveCount(0);
  await expect(page).toHaveURL(/#\/student\/home$/);
  expect((await page.locator('.main-content').boundingBox())!.width).toBe(originalWidth);
  await page.screenshot({ path: info.outputPath('student-persistent-composer.png') });
  await input.fill('下一条还没发');
  await openHistory(page);
  await expect(history(page).locator('.intent-user')).toContainText('删除所有资料');
  await expect(history(page).locator('.intent-answer')).toContainText('尚未理解或执行');
  await history(page).getByRole('button', { name: '收起对话历史' }).click();
  await expect(input).toHaveValue('下一条还没发');
  await expect(input).toBeFocused();
  await expect(history(page)).toHaveCount(0);
  await go(page, 'student/materials');
  await expect(page.getByText('3 道示例题 · 2 道确认错题')).toBeVisible();
  await expect(input).toHaveValue('下一条还没发');
  await openHistory(page);
  await expect(history(page).locator('.intent-user')).toContainText('删除所有资料');
  await page.getByRole('button', { name: '家长手机端', exact: true }).click();
  await expect(input).toHaveValue('');
  await expect(history(page).locator('.intent-user')).toHaveCount(0);
  await page.getByRole('button', { name: '学生平板端', exact: true }).click();
  await expect(input).toHaveValue('下一条还没发');
  await expect(history(page).locator('.intent-user')).toContainText('删除所有资料');
  await page.getByLabel('当前课程空间').selectOption('extension');
  await expect(input).toHaveValue('');
  await expect(history(page).locator('.intent-user')).toHaveCount(0);
});

test('中文输入确认和换行不误发送；断网保留输入，恢复后可发送', async ({ page }) => {
  await go(page, 'student/home');
  const input = page.getByLabel('对 DeerMind 说');
  await input.fill('我想问');
  await input.dispatchEvent('keydown', { key: 'Enter', isComposing: true, bubbles: true });
  await expect(input).toHaveValue('我想问');
  await input.press('End');
  await input.press('Shift+Enter');
  await expect(input).toHaveValue('我想问\n');
  await input.press('a');
  await page.getByRole('button', { name: '走查工具' }).click();
  await page.locator('.review-tools select').selectOption('offline');
  await input.press('Enter');
  await expect(input).toHaveValue('我想问\na');
  await openHistory(page);
  await expect(history(page).locator('.intent-user')).toHaveCount(0);
  await history(page).getByRole('button', { name: '收起对话历史' }).click();
  await page.locator('.review-tools select').selectOption('normal');
  await page.getByRole('button', { name: '发送对话' }).click();
  await expect(input).toHaveValue('');
  await expect(history(page)).toHaveCount(0);
  await openHistory(page);
  await expect(history(page).locator('.intent-user')).toHaveText('我想问\na');
});

test('从状态依据进入当前回复，安排验证后才开始，全程不自动展开历史', async ({ page }, info) => {
  await go(page, 'student/home');
  await page.getByRole('button', { name: '查看章节：百分数的应用' }).click();
  await page.getByRole('button', { name: '为什么这样判断？', exact: true }).click();
  await expect(page.getByLabel('对 DeerMind 说')).toBeFocused();
  await expect(dock(page).locator('.conversation-context')).toContainText('百分数的应用');
  await expect(dock(page).locator('.intent-answer')).toContainText('还需了解');
  await expect(history(page)).toHaveCount(0);
  await example(page, '我想验证一下理解');
  await expect(dock(page).locator('.intent-answer')).toContainText('固定题单 2 题');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
    true,
  );
  await page.screenshot({ path: info.outputPath('student-current-confirmation.png') });
  await dock(page).getByRole('button', { name: '按此安排开始' }).click();
  await expect(page.getByRole('heading', { name: '第 1 题 / 共 2 题' })).toBeVisible();
  await expect(page.locator('.problem-text')).toContainText('25%');
  await expect(history(page)).toHaveCount(0);
});

test('对话求助不提前泄露答案，取消后继续检测，确认才结束并给提示', async ({ page }) => {
  await go(page, 'student/test');
  await page.getByLabel('百分数的应用', { exact: true }).check();
  await page.getByRole('button', { name: '开始本次自测' }).click();
  await example(page, '这次表现说明了什么？');
  await expect(dock(page).locator('.intent-answer')).toContainText('先不展开');
  await example(page, '只给我一点提示');
  await expect(dock(page).locator('.intent-answer')).not.toContainText('分母为 100');
  await dock(page).getByRole('button', { name: '暂时不做' }).click();
  await expect(page.getByRole('heading', { name: '第 1 题 / 共 2 题' })).toBeVisible();
  await example(page, '只给我一点提示');
  await dock(page).getByRole('button', { name: '结束检测，只看提示' }).click();
  await expect(dock(page).locator('.intent-answer')).toContainText('分母为 100');
  await expect(dock(page).locator('.intent-answer')).not.toContainText('1/4');
  await expect(history(page)).toHaveCount(0);
  await page.getByRole('button', { name: '收起当前回复' }).click();
  await go(page, 'student/results');
  await expect(page.locator('.result-stats')).toContainText('2未检测');
});

test('资料替换后旧删除卡不可执行，重新明确对象后执行并同步资料页', async ({ page }) => {
  await go(page, 'student/home');
  await example(page, '删除当前这份资料');
  await page.getByRole('button', { name: '收起当前回复' }).click();
  await go(page, 'student/upload');
  await page.getByRole('button', { name: '使用示例试卷继续' }).click();
  await expect(page.getByText('3 道示例题 · 2 道确认错题')).toBeVisible();
  await openHistory(page);
  await expect(dock(page).getByRole('button', { name: '确认删除这份资料' })).toBeDisabled();
  await history(page).getByRole('button', { name: '收起对话历史' }).click();
  await example(page, '删除当前这份资料');
  await dock(page).getByRole('button', { name: '确认删除这份资料' }).click();
  await expect(page.getByRole('heading', { name: '这份资料已从你的界面移除' })).toBeVisible();
  await expect(dock(page).getByText('已完成上述操作')).toBeVisible();
});

test('管理员从常驻输入区建立候选，不直接批准或启用', async ({ page }) => {
  await go(page, 'admin/dashboard');
  await expect(page.getByLabel('对 DeerMind 说')).toBeVisible();
  await expect(history(page)).toHaveCount(0);
  await example(page, '整理本章的模型维护候选');
  await dock(page).getByRole('button', { name: '建立并查看候选' }).click();
  await expect(page.getByText('候选待检查 · v1')).toBeVisible();
  await expect(page.getByRole('button', { name: '提交并启用此版本' })).toHaveCount(0);
  await example(page, '整理本章的模型维护候选');
  await expect(dock(page).locator('.intent-answer')).toContainText('不覆盖');
  await expect(history(page)).toHaveCount(0);
});

test('家长常驻输入不遮导航，历史按需展开；删除咨询同步清理记录', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await go(page, 'parent/overview');
  await expect(page.getByLabel('对 DeerMind 说')).toBeVisible();
  await expect(history(page)).toHaveCount(0);
  const box = (await dock(page).boundingBox())!;
  const nav = (await page.locator('.bottom-nav').boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(nav.y);
  await page.screenshot({ path: info.outputPath('parent-persistent-composer.png') });
  await page.getByRole('button', { name: '查看章节：百分数的应用' }).click();
  await page.getByRole('button', { name: '为什么这样判断？', exact: true }).click();
  await expect(dock(page).locator('.intent-answer')).toContainText('有 1 题需要回顾');
  await expect(history(page)).toHaveCount(0);
  await openHistory(page);
  await expect(history(page).locator('.intent-answer')).toContainText('有 1 题需要回顾');
  await dock(page).getByRole('button', { name: '情景示例', exact: true }).click();
  await expect(dock(page).getByRole('button', { name: '我想验证一下理解' })).toHaveCount(0);
  await dock(page).getByRole('button', { name: '情景示例', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
    true,
  );
  await page.screenshot({ path: info.outputPath('parent-context-history.png') });
  await history(page).getByRole('button', { name: '收起对话历史' }).click();
  await go(page, 'parent/consult');
  await page.getByRole('button', { name: '删除整段会话', exact: true }).click();
  await page.getByRole('button', { name: '确认删除会话' }).click();
  await openHistory(page);
  await expect(history(page).locator('.intent-user')).toHaveCount(0);
});

test('学生删除原件后，相关回复和历史不能成为恢复原件的入口', async ({ page }) => {
  await go(page, 'student/question');
  await example(page, '讲讲当前这道题');
  await expect(dock(page).locator('.intent-answer')).toContainText('200');
  await page.getByRole('button', { name: '收起当前回复' }).click();
  await go(page, 'student/materials');
  await page.getByRole('button', { name: '删除整份试卷', exact: true }).click();
  await page.getByRole('button', { name: '确认删除整卷' }).click();
  await openHistory(page);
  await expect(dock(page).locator('.intent-answer')).toHaveCount(0);
  await expect(dock(page).getByText('与已删除原资料有关的旧对话内容已同步隐藏。')).toBeVisible();
});
