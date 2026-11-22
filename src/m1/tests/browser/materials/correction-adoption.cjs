// 对同一 C03 样例验证引用修正、草稿恢复、采用和重复提交。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const label = process.env.M1_TEST_RICH_DOMAIN_NAME;

async function run() {
  assert.equal(process.env.M1_E02_REAL_MODEL, 'C03');
  assert.ok(label && evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 920 } });
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const navigation = page.getByRole('navigation', { name: '管理功能' });
    await navigation.waitFor();
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    async function openBook() {
      await navigation.getByRole('button', { name: '教材管理' }).click();
      await page.getByRole('searchbox', { name: '教材名称' }).fill(label);
      await page.getByRole('button', { name: '搜索' }).click();
      await page.getByRole('button', { name: label, exact: true }).click();
    }
    await openBook();
    const assistant = page.getByRole('region', { name: '教材助手' });
    await assistant.getByRole('button', { name: '核对候选', exact: true }).last().click();
    await assistant.getByRole('button', { name: '引用这批候选继续修正' }).click();
    await assistant.getByLabel('给教材助手发消息').fill(
      '本轮范围只包括两张已给图片中可见的那一道分数辨错题，我确认题目内容足够核对。'
      + '题干引用“下面几道题”也请照录，但其余题都在本次范围之外，请勿列为缺口或追问。'
      + '保留原图三行演算与原符号次序，不添加括号或正确解法，不把讨论提示列作解法。'
      + '章节名称沿用上一批，仅就这一道题标记覆盖完整，若画面内确有关键字不可读再列缺口。',
    );
    const accepted = page.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith('/messages'));
    await assistant.getByRole('button', { name: '发送' }).click();
    const response = await accepted;
    assert.equal(response.status(), 202, await response.text());
    const awaited = await response.json();
    const endpoint = response.url();
    const whileBusy = await page.request.post(endpoint, {
      data: { request_id: randomUUID(), message: '这条草稿等待前一轮结束后再发。' }, headers,
    });
    assert.equal(whileBusy.status(), 409, await whileBusy.text());
    assert.equal((await whileBusy.json()).error.code, 'assistant_busy');
    const draft = '暂存草稿，当前先核对上一个结果。';
    await assistant.getByLabel('给教材助手发消息').fill(draft);
    await page.reload();
    await openBook();
    assert.equal(await assistant.getByLabel('给教材助手发消息').inputValue(), draft);

    const proposal = page.getByRole('region', { name: '待核对候选' });
    await proposal.getByRole('button', { name: '采用', exact: true }).waitFor({ timeout: 200_000 });
    const api = new URL(endpoint);
    let latest;
    const deadline = Date.now() + 200_000;
    while (!latest && Date.now() < deadline) {
      const messages = await (await page.request.get(endpoint, { headers })).json();
      latest = messages.items.findLast((item) => item.role === 'assistant'
        && item.turn_ref === awaited.request_ref)?.explicit_refs.find((item) => item.type === 'candidate_batch');
      if (!latest) await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    assert.ok(latest, 'the acceptance should produce its own batch');
    const batchEndpoint = api.href.replace(/\/messages$/, '/candidate-batches/') + latest.id;
    const current = await (await page.request.get(batchEndpoint, { headers })).json();
    assert.equal(current.batch.coverage.complete, true, JSON.stringify(current.batch.coverage));
    assert.ok(current.items.some((item) => item.kind === 'task_instance'));
    assert.ok(!current.items.some((item) => item.kind === 'reference'));
    const previous = current.batch.diff_summary.previous_batch;
    const old = await (await page.request.get(batchEndpoint.replace(latest.id, previous.batch_id), { headers })).json();
    assert.equal(old.batch.decision_state, 'superseded');

    let command;
    let saved;
    await page.route('**/candidate-batches/*/decision', async (route) => {
      command = route.request().postDataJSON();
      const result = await route.fetch();
      assert.equal(result.status(), 200, await result.text());
      saved = await result.json();
      await route.abort();
    });
    await proposal.getByRole('button', { name: '采用', exact: true }).click();
    await page.getByRole('region', { name: '已采用内容' }).waitFor();
    assert.ok(command && saved);
    const repeated = await page.request.post(batchEndpoint + '/decision', { data: command, headers });
    assert.deepEqual(await repeated.json(), saved);
    await writeFile(path.join(evidence, 'C03-corrected.json'), JSON.stringify(current, null, 2), 'utf8');
    await page.screenshot({ path: path.join(evidence, 'C03-adopted.png'), fullPage: true });
    console.log('E02-09/10 browser: quoted correction, busy draft, previous batch, receipt recovery and adoption verified');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
