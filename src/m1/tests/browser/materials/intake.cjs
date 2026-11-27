// 用已采用的真实 C03 候选检查 API、JetStream、Domain 待办与回执。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const label = process.env.M1_TEST_RICH_DOMAIN_NAME;

async function run() {
  assert.ok(evidence && label && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const navigation = page.getByRole('navigation', { name: '管理功能' });
    await navigation.waitFor();
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    await navigation.getByRole('button', { name: '教材管理' }).click();
    await page.getByRole('searchbox', { name: '教材名称' }).fill(label);
    await page.getByRole('button', { name: '搜索' }).click();
    await page.getByRole('button', { name: label, exact: true }).click();
    await page.getByRole('button', { name: '候选与领域入库', exact: true }).click();
    const adopted = page.getByRole('region', { name: '已采用内容' });
    const task = adopted.getByRole('checkbox', { name: /^题目 · / }).first();
    await task.check();
    const sent = page.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith('/intake-submissions'));
    await adopted.getByRole('button', { name: '提交领域入库' }).click();
    const response = await sent;
    assert.equal(response.status(), 202, await response.text());
    const accepted = await response.json();
    const command = response.request().postDataJSON();
    assert.equal(command.adopted_content_refs.length, 1);
    assert.deepEqual(command.parent_bindings, []);
    await adopted.getByText('领域已接收，可在领域管理处理。').waitFor({ timeout: 65_000 });
    const endpoint = response.url();
    const detail = await (await page.request.get(endpoint + '/' + accepted.result.submission_id, { headers })).json();
    assert.equal(detail.status, 'received');
    assert.equal(detail.items.length, 1);
    const repeat = await (await page.request.post(endpoint, { headers, data: command })).json();
    assert.equal(repeat.request_ref, accepted.request_ref);
    assert.deepEqual(repeat.result.items, detail.items);
    const fresh = await page.request.post(endpoint, { headers, data: { ...command, request_id: randomUUID() } });
    assert.equal(fresh.status(), 202, await fresh.text());
    const secondId = (await fresh.json()).result.submission_id;
    let second;
    for (let attempt = 0; attempt < 32; attempt++) {
      second = await (await page.request.get(endpoint + '/' + secondId, { headers })).json();
      if (second.status !== 'submitted') break;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    assert.equal(second.status, 'received');
    assert.deepEqual(second.items, detail.items);
    const duplicate = await page.request.post(endpoint, { headers, data: {
      ...command, request_id: randomUUID(), adopted_content_refs: Array(2).fill(command.adopted_content_refs[0]),
    } });
    assert.equal(duplicate.status(), 409);
    await page.screenshot({ path: path.join(evidence, 'C03-intake-material.png'), fullPage: true });
    await navigation.getByRole('button', { name: '领域管理' }).click();
    await page.getByRole('searchbox', { name: '搜索领域' }).fill(label);
    await page.getByRole('table', { name: '领域列表' }).getByText(label, { exact: true }).click();
    await page.getByRole('button', { name: '待入库内容' }).click();
    const table = page.getByRole('region', { name: '待入库内容' });
    await table.getByRole('cell', { name: '题目', exact: true }).waitFor();
    assert.equal(await table.getByRole('cell', { name: '题目', exact: true }).count(), 1);
    assert.equal(await table.getByRole('cell', { name: '题内参考', exact: true }).count(), 0);
    await page.screenshot({ path: path.join(evidence, 'C03-intake-domain.png'), fullPage: true });
    await writeFile(path.join(evidence, 'C03-intake.json'), JSON.stringify({ accepted, detail, second }, null, 2), 'utf8');
    console.log('E02-11 browser: independent task selection, domain acceptance, replay and deduplication verified');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
