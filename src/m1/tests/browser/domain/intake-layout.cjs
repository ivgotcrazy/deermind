// 使用已有待入库题目检查有数据的操作列。只打开并关闭弹窗，不修改教材。
const assert = require('node:assert/strict');
const { mkdir } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

async function checkRows(panel) {
  const row = panel
    .getByRole('row')
    .filter({ has: panel.page().getByRole('button', { name: '关联任务', exact: true }) })
    .first();
  await row.waitFor();
  const header = await panel
    .getByRole('columnheader')
    .first()
    .evaluate((el) => getComputedStyle(el).backgroundColor);
  const rowColor = await row
    .getByRole('rowheader')
    .evaluate((el) => getComputedStyle(el).backgroundColor);
  assert.notEqual(rowColor, header, '内容单元格使用了列表表头的背景色');
  const buttons = row.getByRole('button');
  assert.equal(await buttons.count(), 3);
  const boxes = [];
  for (const button of await buttons.all()) {
    const box = await button.boundingBox();
    assert.ok(box.height >= 28, '操作目标高度不足');
    for (const previous of boxes) {
      const gapX = Math.max(previous.x - box.x - box.width, box.x - previous.x - previous.width);
      const gapY = Math.max(previous.y - box.y - box.height, box.y - previous.y - previous.height);
      assert.ok(gapX >= 8 || gapY >= 4, '不同操作之间没有可见间距');
    }
    boxes.push(box);
  }
  const refresh = await panel.getByRole('button', { name: '刷新' }).boundingBox();
  const table = await panel.getByRole('table').boundingBox();
  assert.ok(refresh.y + refresh.height + 8 <= table.y, '刷新按钮应位于表格上方的标题栏');
}

async function main() {
  const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
  const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
  const domain = process.env.M1_TEST_INTAKE_DOMAIN ?? 'E04 合成教材 · 增加四分之一';
  assert.ok(evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1519, height: 880 } });
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码', { exact: true }).fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page
      .getByRole('table', { name: '领域列表' })
      .getByRole('button', { name: domain, exact: true })
      .click();
    await page.getByRole('button', { name: '待入库内容', exact: true }).click();
    const panel = page.getByRole('region', { name: '待入库内容' });
    await panel.getByRole('rowheader').first().waitFor();
    for (const width of [1519, 960, 600]) {
      await page.setViewportSize({ width, height: 880 });
      await panel.screenshot({ path: path.join(evidence, 'intake-panel-' + width + '.png') });
      await checkRows(panel);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    }
    await panel.getByRole('button', { name: '刷新' }).click();
    for (const name of ['关联任务', '删除']) {
      await panel.getByRole('button', { name, exact: true }).first().click();
      const dialog = page.getByRole('dialog', { name: '处理待入库内容' });
      await dialog.getByRole('button', { name: '关闭' }).click();
      await dialog.waitFor({ state: 'hidden' });
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
