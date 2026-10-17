import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => { await page.goto('/phase4.html?view=activity'); });

test('常驻输入不展开历史，追问就地显示且不推进段落', async ({ page }) => {
  await page.getByRole('textbox', { name: '向 DeerMind 提问' }).fill('我还有一个问题');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByRole('region', { name: '对话历史', exact: true })).toHaveCount(0);
  await expect(page.getByRole('status')).toContainText('尚未理解或执行');
  await page.getByRole('button', { name: '走查工具', exact: true }).click();
  await page.getByRole('button', { name: '载入当前段追问示例' }).click();
  await expect(page.getByRole('heading', { name: '为什么这两个三角形的面积相等？' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '为什么要除以 2？', exact: true })).toBeVisible();
});

test('讲解暂离及刷新恢复段落和未发送草稿', async ({ page }) => {
  await page.getByRole('button', { name: '继续下一段' }).click();
  await page.getByRole('textbox', { name: '向 DeerMind 提问' }).fill('我的第 2 段草稿');
  await page.getByRole('button', { name: '返回学习' }).click();
  await page.reload();
  await page.getByRole('button', { name: '继续本次讲解', exact: true }).click();
  await expect(page.getByRole('heading', { name: '底和高，要配成一对' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: '向 DeerMind 提问' })).toHaveValue('我的第 2 段草稿');
});

async function openCheck(page: import('@playwright/test').Page) {
  await page.getByRole('button', { name: '继续下一段' }).click();
  await page.getByRole('button', { name: '继续下一段' }).click();
  await page.getByRole('button', { name: '做一次结束检查' }).click();
  await page.getByRole('button', { name: '开始检查', exact: true }).click();
}

test('检测中不泄露参考，暂离刷新恢复，第2题求助结束并展示对应帮助', async ({ page }) => {
  await openCheck(page);
  await page.getByRole('textbox', { name: '检测作答' }).fill('12 × 5 ÷ 2 = 30');
  await page.getByRole('button', { name: '提交本题' }).click();
  await expect(page.getByText('查看预写参考（不等于自动评分）', { exact: true })).toHaveCount(0);
  await page.getByRole('textbox', { name: '检测作答' }).fill('还没想明白');
  await page.getByRole('button', { name: '暂时离开' }).click();
  await page.reload();
  await page.getByRole('button', { name: '继续未结束的检测' }).click();
  await expect(page.getByRole('textbox', { name: '检测作答' })).toHaveValue('还没想明白');
  await page.getByRole('button', { name: '需要讲解，结束检测' }).click();
  await expect(page.getByRole('heading', { name: '检测已结束，现在可以讲解' })).toBeVisible();
  await expect(page.getByText(/最近检测已提交 1 \/ 2 题；1 题未检测/)).toBeVisible();
  await expect(page.locator('.f-followup')).toContainText('三角形面积为 12 平方厘米');
  await page.reload();
  await expect(page.getByRole('button', { name: '提交本题' })).toHaveCount(0);
});

test('完整检测后统一呈现记录，仍不冒充真实掌握判断', async ({ page }) => {
  await openCheck(page);
  await page.getByRole('textbox', { name: '检测作答' }).fill('30，因为要取一半');
  await page.getByRole('button', { name: '提交本题' }).click();
  await page.getByRole('textbox', { name: '检测作答' }).fill('不同意，是 12');
  await page.getByRole('button', { name: '提交本题' }).click();
  await expect(page.getByText(/最近检测已提交 2 \/ 2 题；0 题未检测/)).toBeVisible();
  await expect(page.getByText('查看预写参考（不等于自动评分）', { exact: true })).toHaveCount(2);
  await expect(page.locator('.f-notice')).toContainText('不把未检测当成不会');
});

test('结束后保持回看，家长只读，后台不伪造模型运行', async ({ page }) => {
  await page.getByRole('button', { name: '先到这里' }).click();
  await page.getByRole('button', { name: '返回学习', exact: true }).click();
  await page.getByRole('button', { name: '回看本次讲解', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '向 DeerMind 提问' })).toBeDisabled();
  await expect(page.getByRole('button', { name: '继续下一段' })).toHaveCount(0);
  await page.getByRole('button', { name: '家长', exact: true }).click();
  await expect(page.getByRole('heading', { name: '这次学习发生了什么' })).toBeVisible();
  await expect(page.getByRole('textbox')).toHaveCount(0);
  await page.getByRole('button', { name: '管理员', exact: true }).click();
  await expect(page.getByText('未执行，不能用页面操作代替', { exact: true })).toBeVisible();
});

test('平板与手机宽度布局可用并留存截图', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  for (const width of [1280, 834, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole('textbox', { name: '向 DeerMind 提问' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const bounds = await page.evaluate(() => ({ main: document.querySelector('.f-workspace')!.getBoundingClientRect().bottom, composer: document.querySelector('.f-composer')!.getBoundingClientRect().top }));
    expect(bounds.main).toBeLessThanOrEqual(bounds.composer + 1);
    await page.screenshot({ path: testInfo.outputPath(`chapter-${width}.png`), fullPage: true });
  }
  expect(errors).toEqual([]);
});
