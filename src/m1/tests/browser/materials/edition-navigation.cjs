// Verify the published fixture through both deployed clients. Each role uses its own browser context.
const assert = require('node:assert/strict');
const path = require('node:path');
const { readFileSync, mkdirSync } = require('node:fs');
const { chromium } = require('playwright');

const env = process.env;
const origin = env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const manifest =
  env.M1_TEST_EDITION_MANIFEST ??
  path.join(
    __dirname,
    '../../../deploy/environments/local-wsl/evidence/material-editions/review.json',
  );
const fixed = JSON.parse(readFileSync(manifest, 'utf8'));
const screenshots = env.M1_TEST_EDITION_SCREENSHOTS;
mkdirSync(screenshots, { recursive: true });

async function login(page, route, who) {
  await page.goto(origin + route);
  await page.getByLabel('账号', { exact: true }).fill(env['M1_' + who + '_LOGIN']);
  await page.getByLabel('密码', { exact: true }).fill(env['M1_' + who + '_PASSWORD']);
  await page.getByRole('button', { name: '登录', exact: true }).click();
}

async function imageReady(page) {
  await page.waitForFunction(
    () => document.querySelector('.original-view img')?.naturalWidth > 100,
  );
}

async function admin(browser) {
  const page = await browser.newPage({ viewport: { width: 1029, height: 543 } });
  await login(page, '/admin/', 'ADMIN');
  await page
    .getByRole('navigation', { name: '管理功能' })
    .getByRole('button', { name: '教材管理' })
    .click();
  const name = '教材版本验收 · 第49–50页';
  await page.getByRole('searchbox', { name: '教材名称' }).fill(name);
  await page
    .getByRole('table', { name: '教材列表' })
    .getByRole('button', { name, exact: true })
    .click();
  const area = page.getByRole('region', { name: '教材版本工作区' });
  await area.waitFor();
  await area.getByLabel('内容树版本').waitFor();
  await imageReady(page);
  let right = 0;
  for (const title of ['教材原页', '内容树', '教学提炼']) {
    const header = await area.getByRole('heading', { name: title, exact: true }).boundingBox();
    assert.ok(header && header.y > 0 && header.y + header.height <= 543, title + ' 应在首屏可见');
    assert.ok(header.x >= right && header.x + header.width <= 1029, title + ' 应在本列内可见');
    right = header.x + header.width;
  }
  const views = page.getByRole('navigation', { name: '教材详情视图' });
  assert.equal(await views.count(), 1, '普通教材详情须有明确的视图入口');
  assert.equal(
    await views.getByRole('button', { name: '教材工作台' }).getAttribute('aria-pressed'),
    'true',
  );
  await page.screenshot({ path: path.join(screenshots, 'admin-book-entry.png') });
  await views.getByRole('button', { name: '教材原件' }).click();
  await page.getByRole('button', { name: '补充原件' }).waitFor();
  await views.getByRole('button', { name: '候选与领域入库' }).click();
  await page.getByRole('button', { name: '章节关联', exact: true }).waitFor();
  await page.getByRole('button', { name: '返回教材列表' }).click();
  const row = page
    .getByRole('row')
    .filter({ has: page.getByRole('button', { name, exact: true }) });
  await row.getByRole('button', { name: '查看教材', exact: true }).click();
  assert.equal(
    await views.getByRole('button', { name: '教材工作台' }).getAttribute('aria-pressed'),
    'true',
  );
  await area.waitFor();
  const entry = await page.request.get(origin + '/admin/');
  assert.match(entry.headers()['cache-control'] ?? '', /no-cache/);
  await page.setViewportSize({ width: 1560, height: 980 });
  const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
  const response = await page.request.get(
    origin + '/api/m1/textbooks/' + fixed.textbook + '/editions/' + fixed.tree,
    { headers: { 'X-Expected-Session': session.session_id } },
  );
  assert.equal(response.status(), 200);
  const tree = await response.json();
  await area.getByLabel('内容树版本').selectOption(tree.edition_id);
  const second = tree.nodes.find((n) => n.node_id === fixed.source);
  const wording = second.content.text;
  await area.getByRole('button', { name: wording, exact: true }).click();
  const pager = area.getByRole('combobox', { name: '教材原页' });
  assert.equal(await pager.inputValue(), tree.pages[1].page_id);
  await imageReady(page);
  await area.getByLabel('提炼版本').selectOption(fixed.extraction);
  await area.getByText(/使用目标：.*验收目标/).waitFor();
  await page.screenshot({ path: path.join(screenshots, 'admin-book.png') });
  await area.getByRole('button', { name: '上一页' }).click();
  assert.equal(await pager.inputValue(), tree.pages[0].page_id);
  await page
    .getByRole('navigation', { name: '管理功能' })
    .getByRole('button', { name: '目标管理' })
    .click();
  await page.locator('#target-domain').selectOption(fixed.domain);
  await page.locator('#target-book').selectOption(fixed.textbook);
  await page.getByRole('button', { name: '验收目标甲 · v1' }).click();
  const selection = page.getByRole('combobox', { name: '教学提炼版本' });
  await page.waitForFunction(
    (id) => Array.from(document.querySelectorAll('select')).some((s) => s.value === id),
    fixed.extraction,
  );
  assert.equal(await selection.inputValue(), fixed.extraction);
  assert.doesNotMatch(await selection.innerText(), /草稿/);
  await page.getByText('预览所选版本的章节与任务', { exact: true }).click();
  await page.screenshot({ path: path.join(screenshots, 'admin-goal.png') });
  await page.close();
  return tree;
}

async function student(browser, tree) {
  const page = await browser.newPage({ viewport: { width: 1560, height: 980 } });
  await login(page, '/student/', 'STUDENT');
  const reader = page.locator('.book-reader');
  await reader.waitFor();
  const currentActivity = page.locator('.dialogue-pane h1');
  const before = await currentActivity.innerText();
  const chapter = tree.nodes.find((n) => n.node_id === fixed.chapter);
  const heading = tree.nodes.find(
    (n) => n.parent_id === fixed.chapter && n.node_kind === 'heading',
  );
  const label = chapter.content?.text || heading?.content?.text || '节';
  const directory = reader.getByRole('region', { name: '章节目录' });
  const second = tree.nodes.find((n) => n.node_id === fixed.source);
  const headings = tree.nodes.filter((n) => ['unit', 'chapter', 'section'].includes(n.node_kind));
  assert.equal(await directory.getByRole('listitem').count(), headings.length);
  assert.equal(await directory.getByText(second.content.text, { exact: true }).count(), 0);
  const branch = directory.getByRole('button', { name: /^收起 / }).first();
  const branchName = (await branch.getAttribute('aria-label')).slice('收起 '.length);
  await branch.click();
  assert.ok((await directory.getByRole('listitem').count()) < headings.length);
  await directory.getByRole('button', { name: '展开 ' + branchName, exact: true }).click();
  await directory.getByRole('button', { name: label, exact: true }).click();
  await page.screenshot({ path: path.join(screenshots, 'student-chapters.png') });
  await reader.getByRole('button', { name: '本节学习地图' }).click();
  assert.equal(await reader.getByLabel('章节范围').inputValue(), fixed.chapter);
  await reader.getByRole('button', { name: fixed.task, exact: true }).click();
  const dialog = reader.getByRole('dialog');
  await dialog.getByRole('button', { name: fixed.prerequisite, exact: true }).click();
  await dialog.getByRole('heading', { name: fixed.prerequisite, exact: true }).waitFor();
  await dialog.getByRole('button', { name: '返回上一个任务' }).click();
  await dialog.getByRole('heading', { name: fixed.task, exact: true }).waitFor();
  await page.screenshot({ path: path.join(screenshots, 'student-map.png') });
  await dialog.getByRole('button', { name: '关闭' }).click();
  await reader.getByRole('button', { name: '章节', exact: true }).click();
  await directory.getByRole('button', { name: '查看原页' }).click();
  const pageSelector = reader.getByRole('combobox', { name: '教材原页' });
  assert.equal(await pageSelector.inputValue(), chapter.covered_page_ids[0]);
  await pageSelector.selectOption(tree.pages[1].page_id);
  assert.equal(
    await reader.getByRole('combobox', { name: '教材原页' }).inputValue(),
    tree.pages[1].page_id,
  );
  await imageReady(page);
  assert.equal(await currentActivity.innerText(), before);
  await page.screenshot({ path: path.join(screenshots, 'student-original.png') });
  await reader.getByText('引用本页原文', { exact: true }).click();
  await reader.getByRole('combobox', { name: '选择原文' }).selectOption(fixed.source);
  await reader.getByRole('button', { name: '引用并提问' }).click();
  await page.locator('.citation').getByText(second.content.text, { exact: true }).waitFor();
  assert.equal(await directory.count(), 0);
  assert.equal(await currentActivity.innerText(), before);
  await page.close();
}

(async () => {
  const browser = await chromium.launch({ executablePath: env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const tree = await admin(browser);
    await student(browser, tree);
    console.log('Admin and student book navigation passed.');
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
