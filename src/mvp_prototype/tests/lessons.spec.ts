import { test, expect, type Page } from '@playwright/test';

async function open(page: Page) { await page.goto('/#/student/lesson?lesson=fractions'); }
async function example(page: Page) {
  await page.getByRole('button', { name: '情景示例', exact: true }).click();
  await page.locator('.intent-suggestions button').click();
}

test('章节按学生选择推进，追问就地补充，历史只在主动展开后显示', async ({ page }) => {
  await open(page);
  await expect(page.locator('.intent-composer')).toHaveCount(1);
  await expect(page.getByRole('heading', { name: '分数除法，在问什么？' })).toBeVisible();
  await expect(page.getByRole('button', { name: /为什么商是一个半/ })).toBeDisabled();
  await example(page);
  await page.getByLabel('对 DeerMind 说', { exact: true }).fill('第一段未发送的问题');
  await expect(page.locator('.lesson-followup')).toContainText('这里没有改变原来的大小');
  await expect(page.locator('.lesson-explanation')).toContainText('3/4 除以 1/2');
  await expect(page.getByRole('complementary', { name: 'DeerMind 对话历史' })).toHaveCount(0);
  await page.getByRole('button', { name: '展开对话历史' }).click();
  await expect(page.locator('#lesson-history')).toContainText('为什么要把它们都分成四份');
  await page.getByRole('button', { name: '收起对话历史' }).click();
  await page.getByRole('button', { name: '继续下一段' }).click();
  await expect(page.getByRole('heading', { name: '为什么商是一个半？' })).toBeVisible();
  await expect(page.locator('.lesson-followup')).toHaveCount(0);
  await expect(page.getByLabel('对 DeerMind 说', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: /分数除法，在问什么/ }).click();
  await expect(page.locator('.lesson-followup')).toHaveCount(1);
  await expect(page.getByLabel('对 DeerMind 说', { exact: true })).toHaveValue('第一段未发送的问题');
});

test('离页、刷新与换章保留原位置、追问和草稿，空间之间隔离', async ({ page }) => {
  await open(page);
  await example(page);
  await page.getByRole('button', { name: '继续下一段' }).click();
  await page.getByLabel('对 DeerMind 说', { exact: true }).fill('我还想问剩下的一份');
  await page.getByRole('button', { name: '百分数的应用', exact: true }).click();
  await expect(page.getByLabel('对 DeerMind 说', { exact: true })).toHaveValue('');
  await page.getByLabel('对 DeerMind 说', { exact: true }).fill('原价为什么是整体');
  await page.getByRole('button', { name: '分数除法', exact: true }).click();
  await expect(page.getByRole('heading', { name: '为什么商是一个半？' })).toBeVisible();
  await expect(page.getByLabel('对 DeerMind 说', { exact: true })).toHaveValue('我还想问剩下的一份');
  await page.reload();
  await expect(page.getByLabel('对 DeerMind 说', { exact: true })).toHaveValue('我还想问剩下的一份');
  await page.getByRole('link', { name: '返回教材', exact: true }).click();
  await page.locator('.chapter-row').filter({ hasText: '分数除法' }).getByRole('button', { name: '继续讲解' }).click();
  await expect(page.getByRole('heading', { name: '为什么商是一个半？' })).toBeVisible();
  await page.getByLabel('当前课程空间').selectOption('extension');
  await expect(page.getByRole('region', { name: '保留的章节讲解' })).toHaveCount(0);
  await open(page);
  await expect(page.getByRole('heading', { name: '这个空间还没有章节讲解新样例' })).toBeVisible();
  await expect(page.locator('.lesson-content')).toHaveCount(0);
  await page.getByLabel('当前课程空间').selectOption('school');
  await page.getByRole('button', { name: '继续分数除法', exact: true }).click();
  await expect(page.getByLabel('对 DeerMind 说', { exact: true })).toHaveValue('我还想问剩下的一份');
});

test('任意文字不冒充语义理解，断网不提交或推进，提前结束不宣称掌握', async ({ page }) => {
  await open(page);
  await page.getByRole('button', { name: '走查工具' }).click();
  await page.locator('.review-tools select').selectOption('offline');
  const input = page.getByLabel('对 DeerMind 说', { exact: true });
  await input.fill('我已经完全掌握了，换个章节');
  await page.getByRole('button', { name: '发送对话' }).click();
  await expect(input).toHaveValue('我已经完全掌握了，换个章节');
  await expect(page.locator('.lesson-followup')).toHaveCount(0);
  await page.getByRole('button', { name: '继续下一段' }).click();
  await expect(page.getByRole('heading', { name: '分数除法，在问什么？' })).toBeVisible();
  await page.locator('.review-tools select').selectOption('normal');
  await page.getByRole('button', { name: '发送对话' }).click();
  await expect(page.locator('.lesson-followup')).toContainText('没有理解或回答这句话');
  await expect(input).toHaveValue('');
  await expect(page).toHaveURL(/lesson=fractions/);
  await expect(page.locator('#lesson-history')).toHaveCount(0);
  await page.getByRole('button', { name: '结束本次', exact: true }).click();
  await expect(page.getByRole('region', { name: '本次讲解小结' })).toContainText('独立运用还未检查');
  await expect(input).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('heading', { name: '今天先到这里' })).toBeVisible();
  await page.getByRole('button', { name: '走查工具' }).click();
  await page.getByRole('button', { name: '重置全部演示' }).click();
  await expect(page.locator('.lesson-followup')).toHaveCount(0);
  await expect(input).toBeEnabled();
});

test('自测未结束时不能通过章节或直接网址展示讲解', async ({ page }) => {
  await page.goto('/#/student/test');
  await page.getByLabel('分数除法', { exact: true }).check();
  await page.getByRole('button', { name: '开始本次自测' }).click();
  await page.getByLabel('我的作答').fill('尚未提交的独立尝试');
  await open(page);
  await expect(page.getByRole('heading', { name: '先回到正在进行的自测' })).toBeVisible();
  await expect(page.locator('.lesson-content')).toHaveCount(0);
  await page.getByRole('link', { name: '返回自测' }).click();
  await expect(page.getByLabel('我的作答')).toHaveValue('尚未提交的独立尝试');
  await page.getByRole('link', { name: '我的教材' }).click();
  await page.locator('.chapter-row').filter({ hasText: '分数除法' }).getByRole('button', { name: '打开章节' }).click();
  await expect(page).toHaveURL(/student\/test/);
  await expect(page.getByLabel('我的作答')).toHaveValue('尚未提交的独立尝试');
});

test('语音播放结束不自动推进，返回不自动重播', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'speechSynthesis', { value: {
      speak: (utterance: SpeechSynthesisUtterance) => setTimeout(() => utterance.onend?.call(utterance, new Event('end') as SpeechSynthesisEvent), 0),
      cancel: () => {},
    } });
  });
  await open(page);
  await page.getByRole('button', { name: '试听本段' }).click();
  await expect(page.getByRole('button', { name: '试听本段' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '分数除法，在问什么？' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: '试听本段' })).toBeVisible();
  await expect(page.getByRole('button', { name: /为什么商是一个半/ })).toBeDisabled();
});

for (const [width, height] of [[1280, 800], [800, 1280]]) {
  test(`讲解与常驻输入在 ${width}×${height} 可用`, async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width, height });
    await open(page);
    await example(page);
    await page.getByRole('button', { name: '继续下一段' }).scrollIntoViewIfNeeded();
    // Fixed composer must not prevent the learner from reaching the next action.
    const button = await page.getByRole('button', { name: '继续下一段' }).boundingBox();
    const dock = await page.locator('.lesson-dock').boundingBox();
    expect(button!.y + button!.height).toBeLessThanOrEqual(dock!.y + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(errors).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`lesson-${width}.png`), fullPage: true });
    await page.getByRole('button', { name: '继续下一段' }).click();
    await expect(page.getByRole('heading', { name: '为什么商是一个半？' })).toBeVisible();
  });
}
