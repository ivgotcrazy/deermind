// 用同一个 C03 正式实例检查手动修订、过期检查拒绝、软删除与精确回读。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const label = process.env.M1_TEST_RICH_DOMAIN_NAME;
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;

async function run() {
  assert.equal(process.env.M1_E02_REAL_MODEL, 'C03');
  const accepted = JSON.parse(await readFile(path.join(evidence, 'C03-instance-saved.json'), 'utf8'));
  const repaired = JSON.parse(await readFile(path.join(process.env.M1_E02_REPRESENTATIVE_EVIDENCE, 'C03-candidate.json'), 'utf8'));
  const chain = JSON.parse(await readFile(path.join(process.env.M1_E02_REPRESENTATIVE_EVIDENCE, 'C03-intake-chain.json'), 'utf8'));
  const statement = repaired.items.find((entry) => entry.kind === 'task_instance').body.content;
  const taskRef = (chain.linked.result ?? chain.linked).task_ref;
  const original = accepted.result.object_ref;
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage();
    const api = page.request;
    const root = origin + '/api/m1';
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('navigation', { name: '管理功能' }).waitFor();
    const session = await (await api.get(root + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const domains = await (await api.get(root + '/domains', { headers })).json();
    const domain = domains.items.find((item) => item.name === label).object_ref.object_id;
    const base = root + '/domains/' + domain;
    const instanceUrl = base + '/instances/' + original.id;
    const first = await (await api.get(instanceUrl + '?version=1', { headers })).json();
    const updated = { ...first.content, title: first.content.title + ' · 核对版', statement, task_ref: taskRef };
    const command = { action: 'update', request_id: randomUUID(), instance: updated,
      object_ref: first.instance_ref, expected_version: first.instance_ref.version, change_note: '核对工作名' };
    const noCheck = await api.post(base + '/instances', { headers, data: command });
    assert.equal(noCheck.status(), 409, await noCheck.text());
    const checkId = randomUUID();
    const checked = await api.post(base + '/classification-checks', {
      headers, data: { request_id: checkId, instance: updated, object_ref: first.instance_ref },
    });
    assert.equal(checked.status(), 202, await checked.text());
    const query = new URLSearchParams({ action: 'domain.classify_instance', resource_kind: 'domain',
      resource_id: domain, request_id: checkId });
    let receipt;
    for (const _ of Array(120)) {
      receipt = await (await api.get(root + '/requests/receipt?' + query, { headers })).json();
      if (receipt.receipt_state !== 'accepted') break;
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    assert.equal(receipt.receipt_state, 'completed', JSON.stringify(receipt));
    await writeFile(path.join(evidence, 'C03-manual-classification.json'), JSON.stringify(receipt.result, null, 2));
    const check = receipt.result.check_ref;
    const stale = await api.post(base + '/instances', { headers, data: {
      ...command, classification_check_ref: check, instance: { ...updated, title: '临时改名' },
    } });
    assert.equal(stale.status(), 409, await stale.text());
    assert.equal((await stale.json()).error.code, 'classification_stale');
    const revised = await api.post(base + '/instances', { headers, data: { ...command, classification_check_ref: check } });
    assert.equal(revised.status(), 200, await revised.text());
    const second = (await revised.json()).result;
    assert.equal(second.instance_ref.version, 2);
    assert.deepEqual(second.content.statement, statement);
    const removed = await api.post(base + '/instances', { headers, data: {
      action: 'soft_delete', request_id: randomUUID(), object_ref: second.instance_ref,
      expected_version: 2, change_note: 'E02 历史版本保护回归',
    } });
    assert.equal(removed.status(), 200, await removed.text());
    assert.equal((await removed.json()).result.instance_ref.version, 3);
    assert.equal((await api.get(instanceUrl, { headers })).status(), 404);
    assert.deepEqual(await (await api.get(instanceUrl + '?version=1', { headers })).json(), first);
    assert.deepEqual(await (await api.get(instanceUrl + '?version=2', { headers })).json(), second);
    await writeFile(path.join(evidence, 'C03-instance-versions.json'), JSON.stringify({ first, second }, null, 2));
    console.log('E02-15 C03 修订校验、过期检查拒绝、软删除及历史回读通过');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
