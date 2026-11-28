// Verify the published fixture through both deployed clients. Each role uses its own browser context.
const assert = require('node:assert/strict');
const path = require('node:path');
const { readFileSync, mkdirSync } = require('node:fs');
const { chromium } = require('playwright');

const env = process.env;
const origin = env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const manifest =
  env.M1_TEST_EDITION_MANIFEST ??
  path.join(__dirname, '../../../deploy/environments/local-wsl/evidence/book-models/review.json');
const fixed = JSON.parse(readFileSync(manifest, 'utf8'));
const screenshots =
  env.M1_TEST_EDITION_SCREENSHOTS ?? path.join(__dirname, '../../../.artifacts/edition-navigation');
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

async function checkLegacyKnowledge(page, scope, snapshot) {
  const task = snapshot.teaching.find((item) => item.direct_knowledge.length);
  const concept = task.direct_knowledge[0];
  const panel = scope.getByRole('tabpanel', { name: '知识', exact: true });
  assert.equal(await panel.getByText(concept.meaning, { exact: true }).count(), 0);
  await panel
    .getByRole('list', { name: '知识列表' })
    .getByRole('button', { name: concept.name, exact: true })
    .click();
  const detail = page.getByRole('dialog', { name: concept.name, exact: true });
  await detail.getByText(concept.meaning, { exact: true }).waitFor();
  await detail.getByText(task.name, { exact: true }).waitFor();
  assert.equal(await detail.getByRole('textbox').count(), 0);
  await page.keyboard.press('Escape');
  await detail.waitFor({ state: 'hidden' });
}

async function admin(browser) {
  const page = await browser.newPage({ viewport: { width: 1029, height: 543 } });
  await login(page, '/admin/', 'ADMIN');
  await page
    .getByRole('navigation', { name: '管理功能' })
    .getByRole('button', { name: '教材管理' })
    .click();
  const name = fixed.book_name || '教材版本验收 · 第49–50页';
  await page.getByRole('searchbox', { name: '教材名称' }).fill(name);
  await page
    .getByRole('table', { name: '教材列表' })
    .getByRole('button', { name, exact: true })
    .click();
  const views = page.getByRole('navigation', { name: '教材详情视图' });
  await views.waitFor();
  assert.deepEqual(await views.getByRole('button').allTextContents(), [
    '教材原件',
    '内容树',
    '教学提炼',
    '工作台',
  ]);
  await imageReady(page);
  await page.getByRole('button', { name: '删除原件' }).waitFor();
  await views.getByRole('button', { name: '内容树', exact: true }).click();
  await page.getByRole('heading', { name: '内容树版本' }).waitFor();
  await page.getByRole('button', { name: '创建内容树' }).waitFor();
  await views.getByRole('button', { name: '教学提炼', exact: true }).click();
  await page.getByRole('heading', { name: '教学提炼版本' }).waitFor();
  const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
  const snapshot = await (
    await page.request.get(
      origin + '/api/m1/textbooks/' + fixed.textbook + '/editions/' + fixed.extraction,
      { headers: { 'X-Expected-Session': session.session_id } },
    )
  ).json();
  const published = page
    .getByRole('row')
    .filter({ has: page.getByText('v' + snapshot.number, { exact: true }) });
  await published.getByRole('button', { name: '查看' }).click();
  const area = page.locator('.book-columns');
  await area.waitFor();
  const headings = area.getByRole('heading', { level: 3 });
  assert.deepEqual(await headings.allTextContents(), ['教材原页', '内容树', '教学提炼']);
  for (const size of [
    { width: 1029, height: 635 },
    { width: 1560, height: 980 },
  ]) {
    await page.setViewportSize(size);
    const boxes = await area.locator(':scope > section').evaluateAll((nodes) =>
      nodes.map((n) => {
        const { x, width, height } = n.getBoundingClientRect();
        return { x, width, height };
      }),
    );
    assert.equal(boxes.length, 3);
    boxes.forEach((box, i) => {
      assert.ok(box.width > 215 && box.height >= 330);
      if (i) assert.ok(box.x >= boxes[i - 1].x + boxes[i - 1].width - 1);
    });
  }
  await imageReady(page);
  await checkLegacyKnowledge(page, area, snapshot);
  await page.screenshot({ animations: 'disabled', path: path.join(screenshots, 'admin-book.png') });
  await area.getByRole('tab', { name: '任务', exact: true }).click();
  const title = area.getByRole('button', { name: fixed.task, exact: true });
  await title.click();
  const publishedTask = page.getByRole('dialog', { name: fixed.task });
  await publishedTask.getByText('预期产出', { exact: true }).waitFor();
  assert.equal(await publishedTask.getByRole('textbox').count(), 0);
  await page.keyboard.press('Escape');
  await views.getByRole('button', { name: '教学提炼', exact: true }).click();
  await published.getByRole('button', { name: '复制' }).click();
  const responseForCopy = page.waitForResponse(
    (r) => r.url().endsWith('/' + fixed.extraction) && r.request().method() === 'POST',
  );
  await page
    .getByRole('dialog', { name: '复制版本' })
    .getByRole('button', { name: '复制', exact: true })
    .click();
  const copy = await (await responseForCopy).json();
  const copyRow = page
    .getByRole('row')
    .filter({ has: page.getByText('v' + copy.number, { exact: true }) });
  await copyRow.getByRole('button', { name: '编辑' }).click();
  await area.getByRole('tab', { name: '任务', exact: true }).click();
  await title.click();
  const editing = page.getByRole('dialog', { name: fixed.task });
  await editing.getByRole('button', { name: '编辑', exact: true }).click();
  const newOutput = '验收草稿：写出对应数量并注明单位。';
  await editing.getByRole('textbox', { name: '预期产出' }).fill(newOutput);
  await editing.getByRole('button', { name: '保存草稿' }).click();
  await editing.waitFor({ state: 'hidden' });
  await title.click();
  await editing.getByText(newOutput, { exact: true }).waitFor();
  await page.keyboard.press('Escape');
  await views.getByRole('button', { name: '教学提炼', exact: true }).click();
  await copyRow.getByRole('button', { name: '删除' }).click();
  await page
    .getByRole('dialog', { name: '删除版本' })
    .getByRole('button', { name: '删除', exact: true })
    .click();
  await copyRow.waitFor({ state: 'detached' });
  const response = await page.request.get(
    origin + '/api/m1/textbooks/' + fixed.textbook + '/editions/' + fixed.tree,
    { headers: { 'X-Expected-Session': session.session_id } },
  );
  assert.equal(response.status(), 200);
  const tree = await response.json();
  await views.getByRole('button', { name: '内容树', exact: true }).click();
  const draft = page.getByRole('row').filter({ hasText: '草稿' }).first();
  if (await draft.count()) {
    await draft.getByRole('button', { name: '编辑', exact: true }).click();
    const outline = area.getByRole('tree');
    const root = outline.locator('.node-label').first();
    const marker = '浏览器走查 ' + Date.now();
    await root.click();
    async function addNode(label, sibling = false) {
      await area.getByRole('button', { name: '添加', exact: true }).click();
      const editor = page.getByRole('dialog', { name: '添加内容节点' });
      if (sibling) await editor.getByText('同级节点', { exact: true }).click();
      await editor.getByRole('textbox', { name: '正文', exact: true }).fill(label);
      await editor.getByRole('button', { name: '保存节点' }).click();
      await editor.waitFor({ state: 'hidden' });
      await outline.getByText(label, { exact: true }).click();
    }
    await addNode(marker);
    await addNode(marker + ' 子项');
    await addNode(marker + ' 同级项', true);
    await area.getByRole('button', { name: '编辑', exact: true }).click();
    const editor = page.getByRole('dialog', { name: '编辑内容节点' });
    await editor.getByRole('textbox', { name: '正文', exact: true }).fill(marker + ' 已改');
    await editor.getByRole('button', { name: '保存节点' }).click();
    await editor.waitFor({ state: 'hidden' });
    await outline.getByText(marker, { exact: true }).click();
    const remove = area.getByRole('button', { name: '删除', exact: true });
    await remove.click();
    const confirmation = page.getByRole('dialog', { name: '删除内容节点' });
    await confirmation.getByText(/2 个子节点/).waitFor();
    await confirmation.getByRole('button', { name: '取消' }).click();
    await outline.getByText(marker + ' 已改', { exact: true }).waitFor();
    await remove.click();
    await confirmation.getByRole('button', { name: '删除', exact: true }).click();
    await outline.getByText(marker, { exact: true }).waitFor({ state: 'detached' });
  }
  const menu = page.getByRole('navigation', { name: '管理功能' });
  const headers = { 'X-Expected-Session': session.session_id };
  const domains = await (await page.request.get(origin + '/api/m1/domains', { headers })).json();
  const domainName = domains.items.find((d) => d.object_ref.object_id === fixed.domain).name;
  const version = await (
    await page.request.get(
      origin + '/api/m1/textbooks/' + fixed.textbook + '/editions/' + fixed.extraction,
      { headers },
    )
  ).json();
  async function selectInScope(index, option) {
    await page.locator('.scope .el-select').nth(index).click();
    await page.getByRole('option', { name: option, exact: true }).click();
  }
  await menu.getByRole('button', { name: '领域管理' }).click();
  await page.getByRole('button', { name: domainName, exact: true }).click();
  await selectInScope(0, name);
  await selectInScope(1, '教学提炼 v' + version.number);
  await checkLegacyKnowledge(page, page, version);
  await page.getByRole('tab', { name: '任务', exact: true }).click();
  await page.getByRole('button', { name: fixed.task, exact: true }).click();
  await page.getByRole('dialog').getByText('预期产出', { exact: true }).waitFor();
  await page.screenshot({
    animations: 'disabled',
    path: path.join(screenshots, 'admin-domain.png'),
  });
  await page.keyboard.press('Escape');
  await menu.getByRole('button', { name: '评估管理' }).click();
  await selectInScope(0, domainName);
  await selectInScope(1, name);
  await selectInScope(2, '教学提炼 v' + version.number);
  const suite = page
    .getByRole('row')
    .filter({ hasText: '课堂标准 3' })
    .filter({ hasText: '已发布' });
  await suite.waitFor();
  assert.equal(
    await page
      .locator('.scope .el-select__input')
      .first()
      .evaluate((el) => getComputedStyle(el).borderTopWidth),
    '0px',
  );
  await page.screenshot({
    animations: 'disabled',
    path: path.join(screenshots, 'admin-assessment-list.png'),
  });
  await suite.getByRole('button', { name: '查看' }).click();
  await page.getByRole('button', { name: '查看判据' }).click();
  const criteria = page.getByRole('dialog');
  await criteria.getByText('可观察的学习表现', { exact: true }).waitFor();
  assert.equal(await criteria.getByRole('button', { name: '保存' }).count(), 0);
  await page.screenshot({
    animations: 'disabled',
    path: path.join(screenshots, 'admin-assessment.png'),
  });
  await page.keyboard.press('Escape');
  await menu.getByRole('button', { name: '目标管理' }).click();
  await page.locator('#target-domain').selectOption(fixed.domain);
  await page.locator('#target-book').selectOption(fixed.textbook);
  await page.getByRole('button', { name: (fixed.goal_name || '验收目标甲') + ' · v1' }).click();
  const selection = page.getByRole('combobox', { name: '教学提炼版本' });
  await page.waitForFunction(
    (id) => Array.from(document.querySelectorAll('select')).some((el) => el.value === id),
    fixed.extraction,
  );
  assert.equal(await selection.inputValue(), fixed.extraction);
  if (fixed.assessment)
    await page.waitForFunction(
      (id) => Array.from(document.querySelectorAll('select')).some((el) => el.value === id),
      fixed.assessment,
    );
  await page.screenshot({ animations: 'disabled', path: path.join(screenshots, 'admin-goal.png') });
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
  if (await branch.count()) {
    const branchName = (await branch.getAttribute('aria-label')).slice('收起 '.length);
    await branch.click();
    assert.ok((await directory.getByRole('listitem').count()) < headings.length);
    await directory.getByRole('button', { name: '展开 ' + branchName, exact: true }).click();
  }
  await directory.getByRole('button', { name: label, exact: true }).click();
  await page.screenshot({
    animations: 'disabled',
    path: path.join(screenshots, 'student-chapters.png'),
  });
  await reader.getByRole('button', { name: '本节学习地图' }).click();
  assert.equal(await reader.getByLabel('章节范围').inputValue(), fixed.chapter);
  await reader.getByRole('button', { name: fixed.task, exact: true }).click();
  const dialog = reader.getByRole('dialog');
  if (fixed.prerequisite) {
    await dialog.getByRole('button', { name: fixed.prerequisite, exact: true }).click();
    await dialog.getByRole('heading', { name: fixed.prerequisite, exact: true }).waitFor();
    await dialog.getByRole('button', { name: '返回上一个任务' }).click();
    await dialog.getByRole('heading', { name: fixed.task, exact: true }).waitFor();
  }
  await page.screenshot({
    animations: 'disabled',
    path: path.join(screenshots, 'student-map.png'),
  });
  await dialog.getByRole('button', { name: '关闭' }).click();
  await reader.getByRole('button', { name: '章节', exact: true }).click();
  await directory.getByRole('button', { name: '查看原页' }).click();
  const pageSelector = reader.getByRole('combobox', { name: '教材原页' });
  assert.equal(await pageSelector.inputValue(), chapter.covered_page_ids[0]);
  await pageSelector.selectOption(tree.pages.at(-1).page_id);
  assert.equal(
    await reader.getByRole('combobox', { name: '教材原页' }).inputValue(),
    tree.pages.at(-1).page_id,
  );
  await imageReady(page);
  assert.equal(await currentActivity.innerText(), before);
  await page.screenshot({
    animations: 'disabled',
    path: path.join(screenshots, 'student-original.png'),
  });
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
