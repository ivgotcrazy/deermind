// Verify manual graph editing against a disposable copy on the target cluster.
const assert = require('node:assert/strict');
const { readFileSync, mkdirSync } = require('node:fs');
const { randomUUID } = require('node:crypto');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN || 'http://127.0.0.1:5184';
const evidence = path.resolve(
  __dirname,
  '../../../deploy/environments/local-wsl/evidence/knowledge-tasks',
);
const fixed = JSON.parse(readFileSync(path.join(evidence, 'review.json'), 'utf8'));

async function run(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(12000);
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(origin + '/admin/');
  await page.getByLabel('账号', { exact: true }).fill(process.env.M1_ADMIN_LOGIN);
  await page.getByLabel('密码', { exact: true }).fill(process.env.M1_ADMIN_PASSWORD);
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await page.getByRole('navigation', { name: '管理功能' }).waitFor();
  const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
  const headers = {
    'X-Expected-Session': session.session_id,
    'X-CSRF-Token': session.csrf_token,
    Origin: origin,
  };
  const base = origin + '/api/m1/textbooks/' + fixed.textbook + '/editions/';
  async function read(id) {
    return (await page.request.get(base + id, { headers })).json();
  }
  async function command(v, action) {
    const resp = await page.request.post(base + v.edition_id, {
      headers,
      data: { request_id: randomUUID(), revision: v.revision, action },
    });
    assert.equal(resp.status(), 200, await resp.text());
    return resp.json();
  }
  const published = await read(fixed.extraction);
  const domain = await (
    await page.request.get(
      origin + '/api/m1/domains/' + fixed.domain + '/objects/' + fixed.domain,
      { headers },
    )
  ).json();
  const draft = await command(published, 'copy');
  const openBook = async (v) => {
    await page.goto(
      origin +
        `/admin/?textbook=${fixed.textbook}&tree=${fixed.tree}&extraction=${v.edition_id}#textbooks`,
    );
    await page
      .getByRole('navigation', { name: '教材详情视图' })
      .getByRole('button', { name: '工作台' })
      .click();
    await page.getByRole('tab', { name: '知识', exact: true }).waitFor();
  };
  const button = (scope, name) => scope.getByRole('button', { name, exact: true });
  const dialog = page.locator('.el-drawer[role=dialog]');
  const model = published.teaching,
    baseTask = model.tasks.find((t) =>
      model.tasks.some((s) =>
        s.methods.some((m) => m.dependencies.some((d) => d.task_key === t.key)),
      ),
    );
  const knowledge = model.knowledge.find((k) => k.key === baseTask.knowledge_key);
  const composite = model.tasks.find((t) => t.task_type === 'composite');
  try {
    await openBook(draft);
    const list = page.locator('.teaching-model');
    assert.equal(await list.getByText(knowledge.meaning, { exact: true }).count(), 0);
    await button(list, knowledge.name).click();
    await dialog.getByText(knowledge.meaning, { exact: true }).waitFor();
    await button(dialog, baseTask.name).click();
    await button(dialog, '返回上一项').click();
    await button(dialog, '删除').click();
    await dialog.getByRole('alert').filter({ hasText: '请先调整引用' }).waitFor();
    await page.keyboard.press('Escape');
    await button(list, '新增知识').click();
    await dialog.getByLabel('知识名称', { exact: true }).fill('浏览器配对测试');
    await dialog.getByLabel('含义', { exact: true }).fill('用于检查同步创建与删除');
    await button(dialog, '保存草稿').click();
    await dialog.waitFor({ state: 'hidden' });
    const originalPair = (await read(draft.edition_id)).teaching;
    const added = originalPair.knowledge.find((k) => k.name === '浏览器配对测试');
    assert.ok(added);
    const paired = originalPair.tasks.find((t) => t.knowledge_key === added.key);
    assert.equal(paired.name, '掌握浏览器配对测试');
    await button(list, added.name).click();
    await button(dialog, '编辑').click();
    await dialog.locator('.el-select').first().click();
    await page.getByRole('option', { name: baseTask.name, exact: true }).click();
    await dialog.locator('.el-select').getByText(baseTask.name, { exact: true }).waitFor();
    const [savePair] = await Promise.all([
      page.waitForResponse(
        (r) => r.url() === base + draft.edition_id && r.request().method() === 'POST',
      ),
      button(dialog, '保存草稿').click(),
    ]);
    assert.equal(savePair.status(), 200);
    await dialog.waitFor({ state: 'hidden' });
    const swapped = (await read(draft.edition_id)).teaching.tasks;
    assert.equal(swapped.find((t) => t.key === paired.key).knowledge_key, knowledge.key);
    assert.equal(swapped.find((t) => t.key === baseTask.key).knowledge_key, added.key);
    await button(list, knowledge.name).click();
    await button(dialog, '删除').click();
    await button(page.getByRole('dialog', { name: '确认删除' }), '删除').click();
    await dialog.waitFor({ state: 'hidden' });
    assert.ok(!(await read(draft.edition_id)).teaching.tasks.some((t) => t.key === paired.key));
    await list.getByRole('tab', { name: '任务', exact: true }).click();
    await button(list, composite.name).click();
    await button(dialog, '编辑').click();
    await button(dialog, '添加方法').click();
    const method = dialog.locator('.methods article').last();
    await method.getByLabel('方法名称', { exact: true }).fill('另一种方法');
    await button(method, '添加前置任务').click();
    await method.getByRole('combobox').click();
    await page.getByRole('option', { name: baseTask.name, exact: true }).click();
    await method.getByLabel('依赖原因', { exact: true }).fill('先辨认单位量');
    await button(dialog, '保存草稿').click();
    await dialog.waitFor({ state: 'hidden' });
    const updated = (await read(draft.edition_id)).teaching.tasks.find(
      (t) => t.key === composite.key,
    );
    assert.deepEqual(updated.methods.at(-1).dependencies, [
      { task_key: baseTask.key, reason: '先辨认单位量' },
    ]);
    await button(list, composite.name).click();
    await dialog.getByText('先辨认单位量', { exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(evidence, 'method-dependencies.png'),
      animations: 'disabled',
    });
    await page.keyboard.press('Escape');

    const menu = page.getByRole('navigation', { name: '管理功能' });
    await button(menu, '领域管理').click();
    await button(page, domain.object?.content?.name ?? domain.content.name).click();
    await page.locator('.scope .el-select').first().click();
    await page.getByRole('option', { name: fixed.book_name, exact: true }).click();
    await page.locator('.scope .el-select').last().click();
    await page.getByRole('option', { name: '教学提炼 v' + fixed.version, exact: true }).click();
    await button(list, knowledge.name).click();
    assert.equal(await button(dialog, '编辑').count(), 0);
    await button(dialog, baseTask.name).click();
    await dialog.getByText(baseTask.expected_output, { exact: true }).waitFor();
    assert.equal(await dialog.getByRole('textbox').count(), 0);
    await page.keyboard.press('Escape');
    await list.getByRole('tab', { name: '任务', exact: true }).click();
    await button(list, composite.name).waitFor();
    await page.screenshot({
      path: path.join(evidence, 'domain-tasks.png'),
      animations: 'disabled',
    });
    await openBook(published);
    await button(list, knowledge.name).waitFor();
    await page.waitForFunction(
      () => document.querySelector('.original-view img')?.naturalWidth > 100,
    );
    await page.screenshot({
      path: path.join(evidence, 'workbench-knowledge.png'),
      animations: 'disabled',
    });
    assert.deepEqual((await read(fixed.extraction)).teaching, model);
    assert.deepEqual(errors, []);
  } catch (e) {
    console.error('Screen at failure:', (await page.locator('body').innerText()).slice(-1400));
    throw e;
  } finally {
    await command(await read(draft.edition_id), 'discard');
    await page.close();
  }
}

(async () => {
  mkdirSync(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    await run(browser);
    console.log(
      'PASS paired creation, swap, guarded deletion, method dependencies, read-only published views',
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
