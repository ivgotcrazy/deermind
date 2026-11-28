// Exercise deletion and copying only on objects created by this run.
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const path = require('node:path');
const { readFileSync } = require('node:fs');
const { chromium } = require('playwright');

async function verify(page, origin, fixture) {
  await page.goto(origin + '/admin/');
  await page.getByLabel('账号', { exact: true }).fill(process.env.M1_ADMIN_LOGIN);
  await page.getByLabel('密码', { exact: true }).fill(process.env.M1_ADMIN_PASSWORD);
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await page.getByRole('navigation', { name: '管理功能' }).waitFor();
  const api = origin + '/api/m1';
  const session = await (await page.request.get(api + '/auth/session')).json();
  const headers = {
    'X-Expected-Session': session.session_id,
    'X-CSRF-Token': session.csrf_token,
    Origin: origin,
  };
  async function call(path, data, expected = 200) {
    const response = await page.request.fetch(api + path, {
      method: data ? 'POST' : 'GET',
      headers,
      data,
    });
    assert.equal(response.status(), expected, path + ' ' + (await response.text()));
    return response.json();
  }
  const request = () => ({ request_id: randomUUID() });
  const domain = (
    await call('/domain-definitions', {
      ...request(),
      action: 'create',
      object_kind: 'domain',
      definition: { name: '删除规则走查 ' + randomUUID().slice(0, 8) },
      change_note: '删除规则验收',
    })
  ).result.object_ref;
  const book = (
    await call('/material-imports', {
      ...request(),
      domain_ref: domain,
      files: [],
      title: '清理测试教材',
      source: '合成材料',
    })
  ).result;
  const removeDomain = (expected) =>
    call(
      '/domain-definitions',
      {
        ...request(),
        action: 'soft_delete',
        object_kind: 'domain',
        object_ref: domain,
        expected_version: domain.version,
        change_note: '清理本次验收领域',
      },
      expected,
    );
  await removeDomain(409);
  const info = (await call('/textbooks/' + book.textbook_id)).import;
  await call('/material-imports/' + book.import_id + '/delete', {
    ...request(),
    expected_revision: info.revision,
    confirmed_scope_ref: info.deletion_scope_ref,
  });
  await removeDomain(200);

  const path = '/textbooks/' + fixture.textbook + '/editions/';
  const source = await call(path + fixture.extraction);
  const edit = (version, action, expected = 200) =>
    call(path + version.edition_id, { ...request(), action, revision: version.revision }, expected);
  // Save a child and a grandchild to a disposable draft. Stale writes cannot
  // overwrite a later edit, and removing the branch leaves the source intact.
  const original = await call(path + fixture.tree);
  let draft = await edit(original, 'copy');
  const detail = await call(path + draft.edition_id);
  const root = detail.nodes.find((n) => !n.parent_id);
  const node = {
    node_id: randomUUID(),
    parent_id: root.node_id,
    node_kind: 'paragraph',
    content: { text: '手工补入的说明' },
    covered_page_ids: root.covered_page_ids,
    sibling_order:
      Math.max(
        0,
        ...detail.nodes.filter((n) => n.parent_id === root.node_id).map((n) => n.sibling_order),
      ) + 1,
  };
  const child = { ...node, node_id: randomUUID(), parent_id: node.node_id, sibling_order: 1 };
  const change = (v, nodes, expected = 200) =>
    call(
      path + v.edition_id,
      { ...request(), action: 'edit_tree', revision: v.revision, nodes },
      expected,
    );
  let nodes = [...detail.nodes, node, child];
  const prior = draft;
  draft = await change(draft, nodes);
  await change(prior, detail.nodes, 409);
  nodes = nodes.map((n) =>
    n.node_id === child.node_id ? { ...n, content: { text: '已人工修正' } } : n,
  );
  draft = await change(draft, nodes);
  assert.equal(
    (await call(path + draft.edition_id)).nodes.find((n) => n.node_id === child.node_id).content
      .text,
    '已人工修正',
  );
  draft = await change(draft, detail.nodes);
  assert.equal((await call(path + draft.edition_id)).nodes.length, original.nodes.length);
  await edit(draft, 'discard');
  assert.deepEqual((await call(path + fixture.tree)).nodes, original.nodes);
  const copy = await edit(source, 'copy');
  await edit(copy, 'copy', 409);
  const published = await edit(copy, 'publish');
  const independent = await call(path + published.edition_id);
  assert.notEqual(independent.entries[0].task_ref.object_id, source.entries[0].task_ref.object_id);
  const models = await call(
    '/evaluation/textbooks/' +
      fixture.textbook +
      '/extractions/' +
      published.edition_id +
      '/models',
  );
  assert.deepEqual(models, []);
  const member = independent.entries[0].task_ref;
  await call(
    '/domain-definitions',
    {
      ...request(),
      action: 'soft_delete',
      object_kind: 'task',
      object_ref: member,
      expected_version: member.version,
      change_note: '检验已发布成员只读',
    },
    409,
  );
  await edit(independent, 'discard');
  await call(path + independent.edition_id, undefined, 404);
  await edit(source, 'discard', 409);
  console.log('PASS direct deletion guards, isolated copies, immutable members and retirement');
}

(async () => {
  const fixture = JSON.parse(
    readFileSync(
      process.env.M1_TEST_EDITION_MANIFEST ??
        path.join(
          __dirname,
          '../../../deploy/environments/local-wsl/evidence/book-models/review.json',
        ),
      'utf8',
    ),
  );
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    await verify(
      await browser.newPage(),
      process.env.M1_TEST_DOMAIN_ORIGIN || 'http://127.0.0.1:5184',
      fixture,
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
