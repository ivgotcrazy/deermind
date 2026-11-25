// Build a representative two-chapter target using saved K3s textbook material.
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

async function run() {
  const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
  const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
  assert.ok(origin && evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  const page = await browser.newPage({ viewport: { width: 1360, height: 1020 } });
  try {
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const nav = page.getByRole('navigation', { name: '管理功能' });
    await nav.waitFor();
    const root = origin + '/api/m1';
    const session = await (await page.request.get(root + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    async function call(method, pathname, data, status = 200) {
      const response = await page.request.fetch(root + pathname, { method, headers, data });
      assert.equal(response.status(), status, await response.text());
      return response.json();
    }
    const read = pathname => call('GET', pathname);
    const post = (pathname, data, status) => call('POST', pathname, data, status);
    const { items: books } = await read('/textbooks?limit=100');
    let book, selectedChapters;
    for (const item of books) {
      const content = await read(`/material-imports/${item.import_id}/contents`);
      if (content.chapters.length) {
        book = item;
        selectedChapters = content.chapters.slice(0, 2);
        break;
      }
    }
    assert.ok(book, 'A saved textbook with an adopted chapter is required');
    const { domain_id, textbook_id } = book;
    async function define(kind, definition) {
      const result = await post('/domain-definitions', {
        request_id: randomUUID(), object_kind: kind, definition, domain_id,
        action: 'create', change_note: 'E03-03 走查',
      });
      return result.result.object_ref;
    }
    const stamp = randomUUID().slice(0, 6);
    const methods = [
      await define('solution', { name: '先求增加量 ' + stamp }),
      await define('solution', { name: '先求新量倍数 ' + stamp }),
    ];
    const task_ref = await define('task', {
      name: '已知原量和增加比例 ' + stamp, method_refs: methods,
      applicability: {
        schema_version: '1',
        role: 'definition',
        blocks: [{
          block_id: 'condition', type: 'paragraph',
          payload: { spans: [{ type: 'text', text: '增加比例是小于 1 的正分数。' }] },
          provenance: { source_refs: [], transformation: 'generated' },
        }],
        data_tables: [], source_refs: [],
      },
    });
    const chapters = selectedChapters.map(chapter => chapter.chapter_id);
    for (const [index, chapter] of chapters.entries())
      await post(`/textbooks/${textbook_id}/chapters/${chapter}/associations`, {
        request_id: randomUUID(), action: 'add', task_ref,
        method_refs: chapters.length === 1 ? methods : [methods[index]],
      });
    const { result: claim } = await post('/evaluation/claim-commands', {
      request_id: randomUUID(), action: 'create_claim', domain_id, task_ref,
      title: '评价两种方法 ' + stamp, description: '独立回答并解释使用的比例关系。',
      aspects: [
        { code: 'independent', label: '独立', description: '独立列式' },
        { code: 'understanding', label: '理解', description: '解释列式' },
        { code: 'transfer', label: '迁移', description: '应用于新题' },
        { code: 'retention', label: '保持', description: '间隔后作答' },
      ],
    });
    const claim_ref = claim.claim_ref;
    const item = {
      title: '四分之一', claim_ref, chapter_refs: chapters, method_mode: 'each',
      task_conditions: { description: '只考察增加四分之一' },
      methods: methods.map((method_ref, index) => ({
        method_ref, chapter_refs: [chapters[index] ?? chapters[0]],
        aspects: [{ aspect_ref: { claim_ref, aspect_code: 'independent' }, condition_values: {} }],
      })),
    };
    const command = { request_id: randomUUID(), action: 'create', textbook_id, title: '四分之一 ' + stamp, items: [item] };
    const route = '/learning-targets';
    const initial = await post(route, command);
    const original = initial.result.target;
    assert.deepEqual(original.items[0].task_conditions, item.task_conditions);
    assert.deepEqual(await post(route, command), initial);
    assert.deepEqual(original.items[0].methods.map(m => m.chapter_refs), [[chapters[0]], [chapters[1] ?? chapters[0]]]);
    const target_id = original.target_ref.target_id;
    const rev = { ...command, request_id: randomUUID(), action: 'update', target_id, expected_revision: 1 };
    const falseOrigin = { ...item, methods: [{ ...item.methods[0], chapter_refs: [chapters[1] ?? randomUUID()] }, item.methods[1]] };
    const bad = await post(route, { ...rev, items: [falseOrigin] }, 409);
    assert.equal(bad.error.code, 'invalid_reference');
    const inventedValue = { ...item, task_conditions: { ...item.task_conditions, parameter_values: { 比例: 0.25 } } };
    const rejected = await post(route, { ...rev, request_id: randomUUID(), items: [inventedValue] }, 400);
    assert.equal(rejected.error.code, 'invalid_request');
    const updated = await post(route, { ...rev, request_id: randomUUID(), items: [{
      ...item, item_id: original.items[0].item_id, method_mode: 'any_one',
    }] });
    assert.equal(updated.result.target.target_ref.revision, 2);
    assert.equal(updated.result.target.items[0].method_mode, 'any_one');
    assert.deepEqual((await read(`${route}/${target_id}?revision=1`)).target, original);
    await nav.getByRole('button', { name: '目标管理' }).click();
    const workspace = page.getByRole('region', { name: '目标管理' });
    await workspace.getByLabel('领域', { exact: true }).selectOption(domain_id);
    await workspace.getByLabel('教材').selectOption(textbook_id);
    await workspace.getByRole('button', { name: command.title + ' · v2' }).click();
    await workspace.getByLabel('达标方式').waitFor();
    assert.equal(await workspace.getByLabel('达标方式').inputValue(), 'any_one');
    assert.equal(await workspace.getByLabel('任务范围').inputValue(), '只考察增加四分之一');
    await page.screenshot({ path: path.join(evidence, 'target-two-chapters.png'), fullPage: true });
    await writeFile(path.join(evidence, 'target-two-chapters.json'), JSON.stringify({
      textbook_id, domain_id, import_id: book.import_id, chapter_refs: chapters, target: updated.result.target,
    }, null, 2));
    console.log(`Verified method scope (${chapters.length} chapter(s)), textual conditions, historical revisions and target UI.`);
  } finally {
    await browser.close();
  }
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
