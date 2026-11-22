// 使用一份合成导入验证确认范围、撤下、收据及原件保留。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const fixture = path.resolve(__dirname, '../../../../mvp_foundation/m1/content-representation/round2/inputs/C03-0.png');

async function run() {
  assert.ok(evidence);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const api = page.request;
    const root = origin + '/api/m1';
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const nav = page.getByRole('navigation', { name: '管理功能' });
    await nav.waitFor();
    const session = await (await api.get(root + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const name = 'E02-17 删除回归 ' + randomUUID();
    const setup = await api.post(root + '/domain-definitions', {
      headers, data: { request_id: randomUUID(), action: 'create', object_kind: 'domain',
        change_note: 'E02-17 合成验证', definition: { name } },
    });
    assert.equal(setup.status(), 200, await setup.text());
    const domain = (await setup.json()).result.object_ref.object_id;
    await nav.getByRole('button', { name: '教材管理' }).click();
    await page.getByRole('button', { name: '上传教材' }).click();
    const dialog = page.getByRole('dialog', { name: '上传教材' });
    await dialog.getByLabel('所属领域').selectOption(domain);
    await dialog.getByLabel('教材名称').fill(name);
    await dialog.getByLabel('来源说明').fill('E02-17 会撤下的验收教材');
    await dialog.getByLabel('教材文件').setInputFiles(fixture);
    await dialog.getByRole('button', { name: '上传并登记' }).click();
    await page.getByRole('button', { name: '删除导入' }).waitFor();
    const books = await (await api.get(root + '/textbooks?name=' + encodeURIComponent(name), { headers })).json();
    const book = books.items.find((item) => item.metadata.title === name);
    const reading = root + '/textbooks/' + book.textbook_id;
    let assistantReceipt;
    if (process.env.M1_E02_CANCEL_QUEUED === '1') {
      // Worker 暂停时保存一条不含明确原件范围的请求，验证取消不会外发模型。
      const requestId = randomUUID();
      const accepted = await api.post(root + '/material-imports/' + book.import_id + '/messages', {
        headers, data: { request_id: requestId, message: '等待撤下的教材助手测试消息。' },
      });
      assert.equal(accepted.status(), 202, await accepted.text());
      assistantReceipt = root + '/requests/receipt?' + new URLSearchParams({
        action: 'product.converse_material_assistant', resource_kind: 'material_import',
        resource_id: book.import_id, request_id: requestId,
      });
      const queued = await api.get(assistantReceipt, { headers });
      assert.equal((await queued.json()).receipt_state, 'accepted');
    }
    const recorded = (await (await api.get(reading, { headers })).json()).import;
    const endpoint = root + '/material-imports/' + book.import_id + '/delete';
    const denied = await api.post(endpoint, { headers, data: {
      request_id: randomUUID(), expected_revision: recorded.revision + 1,
      confirmed_scope_ref: recorded.deletion_scope_ref,
    } });
    assert.equal(denied.status(), 409, await denied.text());
    await page.getByRole('button', { name: '删除导入' }).click();
    const confirmation = page.getByRole('dialog', { name: '删除教材导入' });
    const completed = page.waitForResponse((response) => response.url() === endpoint);
    await confirmation.getByRole('button', { name: '确认删除' }).click();
    const response = await completed;
    assert.equal(response.status(), 200, await response.text());
    await page.getByText('教材导入已删除。').waitFor();
    const result = await response.json();
    const replay = await api.post(endpoint, { headers, data: response.request().postDataJSON() });
    assert.deepEqual(await replay.json(), result);
    assert.equal((await api.get(reading, { headers })).status(), 404);
    const item = recorded.sources[0];
    const download = root + '/resource-files?' + new URLSearchParams({
      owner_ref: JSON.stringify(item.source_ref), storage_ref: item.receipt.storage_ref, view: 'source',
    });
    const preserved = await api.get(download, { headers });
    assert.equal(preserved.status(), 200, await preserved.text());
    assert.ok((await preserved.body()).length > 0);
    if (assistantReceipt) {
      const receipt = await api.get(assistantReceipt, { headers });
      assert.equal(receipt.status(), 200, await receipt.text());
      const terminal = await receipt.json();
      assert.equal(terminal.receipt_state, 'completed');
      assert.equal(terminal.result.outcome, 'cancelled');
      await writeFile(path.join(evidence, 'material-cancelled-receipt.json'), JSON.stringify(terminal, null, 2));
    }
    await page.screenshot({ path: path.join(evidence, 'material-deleted.png'), fullPage: true });
    await writeFile(path.join(evidence, 'material-deletion-receipt.json'), JSON.stringify(result, null, 2));
    console.log('E02-17: stale scope rejected, deletion replayed, historical original retained');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
