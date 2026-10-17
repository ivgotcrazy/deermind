import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const sourceReferences = JSON.parse(readFileSync(new URL('../../mvp_foundation/content/fractions-application/source-references.json', import.meta.url), 'utf8')) as {
  diagrams: { id: string; title: string; rows: unknown[] }[];
  rows: { id: string; page: number; diagram_ref: string | null }[];
};

test('实际章节候选可追溯查看，不能从只读审阅误发布或写入学习状态', async ({ page }) => {
  await page.goto('/phase4.html?role=admin&view=maintenance');
  const before = await page.evaluate(() => JSON.stringify(localStorage));
  const content = page.getByTestId('actual-content-review');
  await content.locator('summary').first().click();
  await expect(content).toContainText('尚未发布、采用');
  await expect(content).toContainText('部分比例通过图形给出');
  await content.getByRole('button', { name: '问题与解法', exact: true }).click();
  await content.getByLabel('选择问题模板').selectOption('PT-FA-CHAIN');
  await expect(content).toContainText('先求中间量再求末级量');
  await expect(content).toContainText('先合并逐级份额');
  await content.getByRole('button', { name: '学习要求', exact: true }).click();
  await content.getByText('查看判断依据与限制', { exact: true }).nth(1).click();
  await expect(content).toContainText('系统已给关系式后只完成计算');
  await content.getByRole('button', { name: '评价案例', exact: true }).click();
  await expect(content).toContainText('CASE-051');
  await expect(content.getByRole('button', { name: /发布|采用|批准/ })).toHaveCount(0);
  const after = await page.evaluate(() => JSON.stringify(localStorage));
  expect(after).toBe(before);
  for (const width of [1280, 834, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const overflowing = await content.evaluate(el => el.scrollWidth > el.clientWidth + 1);
    expect(overflowing).toBe(false);
  }
});

test('教材参考按页定位，区分图示条件与推导答案，图形保持可读且不写入状态', async ({ page }) => {
  await page.goto('/phase4.html?role=admin&view=maintenance');
  const before = await page.evaluate(() => JSON.stringify(localStorage));
  const content = page.getByTestId('actual-content-review');
  await content.locator('summary').first().click();
  await content.getByRole('button', { name: '教材题与图示', exact: true }).click();
  const reference = page.getByTestId('source-reference-review');
  await reference.getByLabel('题目位置').selectOption('REF-FA-51-02');
  await expect(reference).toContainText('三等份中的第二个刻度');
  await reference.getByText('展开解答与关系图', { exact: true }).click();
  await expect(reference).toContainText('18 个');
  await expect(reference).toContainText('原题没有直接写出足球占排球 2/3');
  await expect(reference).toContainText('不能直接用作无提示检测题');

  for (const diagram of sourceReferences.diagrams) {
    const row = sourceReferences.rows.find(r => r.diagram_ref === diagram.id)!;
    await reference.getByLabel('教材页码').selectOption(String(row.page));
    await reference.getByLabel('题目位置').selectOption(row.id);
    await reference.locator('details').evaluate(el => { (el as HTMLDetailsElement).open = true; });
    await expect(reference.getByRole('img')).toBeVisible();
    await expect(reference.getByRole('img')).toHaveAccessibleName(new RegExp(diagram.title));
    expect(await reference.locator('svg rect').count()).toBe(diagram.rows.length);
  }
  for (const width of [1280, 834, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await reference.evaluate(el => el.scrollWidth > el.clientWidth + 1)).toBe(false);
    expect(await reference.locator('svg').evaluate(el => el.getBoundingClientRect().width)).toBeGreaterThanOrEqual(599);
  }
  await reference.getByLabel('教材页码').selectOption('55');
  await reference.getByLabel('题目位置').selectOption('REF-FA-55-02');
  await expect(reference).toContainText('本包未设正式评价映射；不等于超纲');
  await expect(reference.locator('details')).not.toHaveAttribute('open', '');
  expect(await page.evaluate(() => JSON.stringify(localStorage))).toBe(before);
});
