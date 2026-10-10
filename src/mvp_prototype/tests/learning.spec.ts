import { test, expect, type Page } from '@playwright/test';
async function go(page: Page, path: string) {
  await page.goto(`/#/${path}`);
}
const metrics = (page: Page) =>
  page.getByRole('region', { name: '按教材查看学习情况' }).locator('.learning-metrics');
const chapter = (page: Page, name: string) =>
  page.getByRole('button', { name: `查看章节：${name}` });

test('教材数字可筛选章节，详情追溯题目并进入学习，聊天带上章节', async ({ page }, info) => {
  await go(page, 'student/learning');
  await expect(metrics(page)).toContainText('33');
  await expect(metrics(page)).toContainText('1 / 3 题已判定答对');
  await expect(page.locator('.chapter-learning')).not.toContainText('能力');
  await expect(page.locator('.learning-chapter')).toHaveCount(2);
  await page.screenshot({ path: info.outputPath('chapter-overview-tablet.png') });
  await metrics(page)
    .getByRole('button', { name: /待回顾的题/ })
    .click();
  await expect(
    page.getByRole('group', { name: '筛选章节' }).getByRole('button', { name: '有待回顾 2' }),
  ).toHaveAttribute('aria-pressed', 'true');
  await chapter(page, '百分数的应用').click();
  const detail = page.getByRole('region', { name: '百分数的应用详情' });
  await expect(page.locator('.conversation-context')).toContainText('百分数的应用');
  await expect(detail.getByLabel('本章记录分布')).toContainText('2 题');
  await detail.getByRole('button', { name: /其中待回顾/ }).click();
  await expect(detail.locator('.chapter-record')).toHaveCount(1);
  await page.screenshot({ path: info.outputPath('chapter-detail-tablet.png') });
  await detail.getByRole('button', { name: '查看相关题目：已知部分求整体' }).click();
  await expect(page.getByRole('dialog')).toContainText('160 × 80% = 128');
  await page.getByRole('button', { name: '打开题目，继续学习' }).click();
  await expect(page).toHaveURL(/student\/question$/);
  await expect(page.locator('.problem-text')).toContainText('八折');
});

test('未确认题排除分母，无记录不显示零分；帮助和未核验检测不虚增答对率', async ({ page }) => {
  await go(page, 'student/upload');
  await page.getByRole('button', { name: '走查工具' }).click();
  await page.locator('.review-tools select').selectOption('partial');
  await page.getByRole('button', { name: '使用示例试卷继续' }).click();
  await expect(page.getByText('3 道示例题 · 1 道确认错题 · 1 道待确认')).toBeVisible();
  await go(page, 'student/learning');
  await expect(metrics(page)).toContainText('50');
  await expect(metrics(page)).toContainText('1 / 2 题已判定答对');
  await metrics(page)
    .getByRole('button', { name: /待确认的题/ })
    .click();
  await expect(page.locator('.learning-chapter')).toHaveCount(1);
  await expect(chapter(page, '分数除法')).toContainText('—');
  await chapter(page, '分数除法').click();
  await page.getByRole('button', { name: /相关题目/ }).click();
  await expect(page.locator('.chapter-record')).toContainText('待确认');
  await page.getByLabel('当前课程空间').selectOption('extension');
  await go(page, 'student/learning');
  await expect(metrics(page).getByRole('button', { name: /资料答对率/ })).toContainText('—');
  await expect(page.locator('.chapter-learning')).not.toContainText('分数除法');
  await page.getByLabel('当前课程空间').selectOption('school');
  await go(page, 'student/question');
  await page.getByRole('button', { name: '只给提示', exact: true }).click();
  await go(page, 'student/learning');
  await chapter(page, '百分数的应用').click();
  await expect(page.locator('.chapter-breakdown')).toContainText('查看过教学帮助1 题');
  await expect(metrics(page)).toContainText('1 / 2 题已判定答对');
  await go(page, 'student/test');
  await page.getByLabel('分数除法', { exact: true }).check();
  await page.getByRole('button', { name: '开始本次自测' }).click();
  await go(page, 'student/learning');
  await expect(page.getByRole('button', { name: '继续当前自测' })).toBeVisible();
  await expect(page.locator('.learning-metrics')).toHaveCount(0);
  await page.getByRole('button', { name: '继续当前自测' }).click();
  await page.getByLabel('我的作答').fill('这条输入尚未核验');
  await page.getByRole('button', { name: '提交并结束' }).click();
  await go(page, 'student/learning');
  await expect(metrics(page)).toContainText('1 / 2 题已判定答对');
  await expect(page.locator('.learning-pending-note')).toContainText('1 次检测作答');
});

test('删除保留统计但不恢复学生原件，家长只读；纠正更新数字而非虚报进步', async ({ page }, info) => {
  await go(page, 'student/materials');
  await page.getByRole('button', { name: '删除整份试卷', exact: true }).click();
  await page.getByRole('button', { name: '确认删除整卷' }).click();
  await go(page, 'student/learning');
  await expect(metrics(page)).toContainText('1 / 3 题已判定答对');
  await chapter(page, '分数除法').click();
  await page.getByRole('button', { name: /相关题目/ }).click();
  await expect(page.locator('.chapter-record')).toHaveCount(0);
  await expect(page.locator('.chapter-detail')).toContainText('原题与原作答不再展示');
  await go(page, 'parent/overview');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(metrics(page)).toContainText('1 / 3 题已判定答对');
  await chapter(page, '分数除法').click();
  await page.getByRole('button', { name: /相关题目/ }).click();
  await page.getByRole('button', { name: '查看相关题目：分数除法' }).click();
  await expect(page.getByRole('dialog')).toContainText('家长按相关依据权限只读查看');
  await expect(page.getByRole('button', { name: '打开题目，继续学习' })).toHaveCount(0);
  await page.getByRole('button', { name: '关闭对话框' }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
    true,
  );
  await page.screenshot({ path: info.outputPath('chapter-detail-parent.png') });
  await page.getByRole('button', { name: '查看相关依据' }).click();
  await page.getByRole('button', { name: '提报已删资料的识别问题' }).click();
  await go(page, 'admin/issues');
  await page.getByRole('button', { name: '记录开始复核' }).click();
  await page.getByRole('button', { name: '确认依据并执行示例修复' }).click();
  await go(page, 'student/learning');
  await expect(metrics(page)).toContainText('2 / 3 题已判定答对');
  await chapter(page, '分数除法').click();
  await page.getByRole('button', { name: '变化与建议' }).click();
  await expect(page.locator('.chapter-changes')).toContainText('记录修正，不表示刚刚学会');
});
