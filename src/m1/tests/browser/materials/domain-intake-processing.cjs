// 使用 C03 的真实归类产物验证正式入库、原收据、历史版本和章节采用。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const label = process.env.M1_TEST_RICH_DOMAIN_NAME;
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const analysisEvidence = process.env.M1_E02_ANALYSIS_EVIDENCE;

async function run() {
  assert.ok(label && evidence && analysisEvidence);
  const positive = JSON.parse(await readFile(path.join(analysisEvidence, 'C03-matching-definition.json'), 'utf8'));
  const negative = JSON.parse(await readFile(path.join(analysisEvidence, 'C03-mismatched-definition.json'), 'utf8'));
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const api = page.request;
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const navigation = page.getByRole('navigation', { name: '管理功能' });
    await navigation.waitFor();
    const session = await (await api.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const root = origin + '/api/m1';
    const domains = await (await api.get(root + '/domains', { headers })).json();
    const domain = domains.items.find((item) => item.name === label).object_ref.object_id;
    const base = root + '/domains/' + domain;
    const intake = await (await api.get(base + '/intake-items', { headers })).json();
    const source = intake.items.find((entry) => entry.kind === 'task_instance');
    const taskInfo = await (await api.get(base + '/objects?kinds=task&name=' +
      encodeURIComponent('检查分数乘除演算中的错误'), { headers })).json();
    const head = taskInfo.items[0].object_ref;
    const task = { ...head, version: 1 };
    const savedPath = path.join(evidence, 'C03-instance-saved.json');
    const recoveryPath = path.join(evidence, 'C03-intake-command.json');
    let applied;
    let command;
    if (source) {
      command = { request_id: randomUUID(), action: 'associate_task',
        expected_revision: source.item_ref.revision, task_ref: task, classification_check_ref: positive.check_ref };
      const endpoint = base + '/intake-items/' + source.item_ref.id + '/actions';
      const invalid = await api.post(endpoint, { headers, data: {
        ...command, request_id: randomUUID(), classification_check_ref: negative.check_ref,
      } });
      assert.equal(invalid.status(), 409, await invalid.text());
      await writeFile(recoveryPath, JSON.stringify(command, null, 2));
      const saved = await api.post(endpoint, { headers, data: command });
      assert.equal(saved.status(), 200, await saved.text());
      applied = await saved.json();
      await writeFile(savedPath, JSON.stringify(applied, null, 2));
    } else {
      applied = JSON.parse(await readFile(savedPath, 'utf8'));
      command = await readFile(recoveryPath, 'utf8').then(JSON.parse).catch((error) => {
        if (error.code !== 'ENOENT') throw error;
        return null;
      });
    }
    const endpoint = base + '/intake-items/' + applied.result.item_ref.id + '/actions';
    if (command) {
      const duplicate = await api.post(endpoint, { headers, data: command });
      assert.deepEqual(await duplicate.json(), applied);
      const readReceipt = await api.get(root + '/requests/receipt?' + new URLSearchParams({
        action: 'domain.process_intake', request_id: command.request_id,
        resource_kind: 'domain', resource_id: domain,
      }), { headers });
      assert.equal(readReceipt.status(), 200, await readReceipt.text());
      assert.deepEqual((await readReceipt.json()).result, applied.result);
    }
    const exact = applied.result.object_ref;
    const instanceUrl = base + '/instances/' + exact.id;
    const old = await (await api.get(instanceUrl + '?version=1', { headers })).json();
    assert.equal(old.content.task_ref.object_id, task.object_id);
    assert.equal(old.content.statement.role, 'statement');
    assert.deepEqual(old.content.reference_solutions, []);
    assert.ok(old.content.statement.blocks.length > 1);
    const pending = await (await api.get(base + '/intake-items', { headers })).json();
    assert.ok(!pending.items.some((item) => item.item_ref.id === applied.result.item_ref.id));

    async function domainSave(body) {
      const response = await api.post(root + '/domain-definitions', {
        headers, data: { request_id: randomUUID(), change_note: 'E02 章节采用接线验证', ...body },
      });
      assert.equal(response.status(), 200, await response.text());
      return (await response.json()).result.object_ref;
    }
    const methods = [];
    for (const name of ['逐步核对算式变形', '用逆运算检查对应步骤']) {
      const options = await (await api.get(base + '/objects?kinds=solution&name=' + encodeURIComponent(name), { headers })).json();
      methods.push(options.items.find((entry) => entry.name === name)?.object_ref ?? await domainSave({
        action: 'create', object_kind: 'solution', domain_id: domain, definition: { name },
      }));
    }
    const definition = await (await api.get(base + '/objects/' + head.object_id + '?version=' + head.version, { headers })).json();
    const chapterTask = definition.object.content.method_refs.length === 2 ? head : await domainSave({
      action: 'update', object_kind: 'task', object_ref: head, expected_version: head.version,
      definition: { ...definition.object.content, method_refs: methods },
    });
    const books = await (await api.get(root + '/textbooks?name=' + encodeURIComponent(label), { headers })).json();
    const book = books.items.find((item) => item.metadata.title === label);
    const contents = await (await api.get(root + '/material-imports/' + book.import_id + '/contents', { headers })).json();
    const chapter = contents.chapters[0].chapter_id;
    const association = root + '/textbooks/' + book.textbook_id + '/chapters/' + chapter + '/associations';
    const add = { action: 'add', request_id: randomUUID(), task_ref: chapterTask, method_refs: [methods[0]] };
    const priorRelations = await (await api.get(association, { headers })).json();
    let relation = priorRelations.items.find((item) => item.task_ref.object_id === chapterTask.object_id);
    if (!relation) {
      const linked = await api.post(association, { headers, data: add });
      assert.equal(linked.status(), 200, await linked.text());
      relation = (await linked.json()).result;
    }
    const change = await api.post(association, { headers, data: {
      ...add, action: 'update', request_id: randomUUID(), association_id: relation.association_ref.id,
      expected_revision: relation.association_ref.revision, method_refs: [methods[1]],
    } });
    assert.equal(change.status(), 200, await change.text());
    const associationRead = await (await api.get(association, { headers })).json();
    const updated = associationRead.items.find((entry) => entry.association_ref.id === relation.association_ref.id);
    assert.deepEqual(updated.method_refs, [methods[1]]);
    const remove = await api.post(association, { headers, data: {
      ...add, action: 'remove', request_id: randomUUID(), association_id: relation.association_ref.id,
      expected_revision: relation.association_ref.revision + 1, method_refs: [],
    } });
    assert.equal(remove.status(), 200, await remove.text());
    const current = await (await api.get(association, { headers })).json();
    assert.ok(!current.items.some((entry) => entry.association_ref.id === relation.association_ref.id));

    await navigation.getByRole('button', { name: '领域管理' }).click();
    await page.getByRole('searchbox', { name: '搜索领域' }).fill(label);
    await page.getByRole('list', { name: '领域列表' }).getByText(label, { exact: true }).click();
    await page.getByRole('button', { name: '题目实例' }).click();
    const panel = page.getByRole('region', { name: '题目实例' });
    await panel.getByRole('button', { name: old.content.title + ' · v1', exact: true }).first().click();
    await panel.getByRole('heading', { name: old.content.title + ' · v1' }).waitFor();
    await page.screenshot({ path: path.join(evidence, 'C03-instance.png'), fullPage: true });
    await writeFile(path.join(evidence, 'C03-results.json'),
      JSON.stringify({ applied, old, relation, associationRead }, null, 2));
    console.log('C03正式入库、归类拒绝、收据重放、章节添加编辑取消均通过');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
