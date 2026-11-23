const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
const out = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;

async function run() {
  await mkdir(out, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1360, height: 960 } });
    await page.route('**/presentations', route => route.abort());
    await page.goto(origin + '/student/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_STUDENT_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_STUDENT_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: '退出登录' }).waitFor();
    const entered = page.waitForResponse(response => response.url().endsWith('/learning-spaces/open') && response.ok());
    await page.getByRole('button', { name: /E04 合成教材/ }).first().click();
    const scope = (await (await entered).json()).result.space.space_id;
    const api = origin + '/api/m1';
    const root = api + '/learning-spaces/' + scope;
    const session = await (await page.request.get(api + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };

    async function finish() {
      const received = page.waitForResponse(response => response.url() === root + '/activity-actions' && response.request().method() === 'POST');
      await page.getByRole('button', { name: '结束活动', exact: true }).click();
      const response = await received;
      assert.equal(response.status(), 200, await response.text());
      return (await response.json()).result.current;
    }
    let current = (await (await page.request.get(root + '/conversation?view=current', { headers })).json()).current;
    while (current.current_activity) current = await finish();

    async function send(wording) {
      await page.getByLabel('输入消息').fill(wording);
      const sent = page.waitForResponse(response => response.url() === root + '/inputs' && response.status() === 202);
      await page.getByRole('button', { name: '发送', exact: true }).click();
      const received = await sent;
      const command = received.request().postDataJSON();
      const query = new URLSearchParams({ action: 'interaction.handle_input', request_id: command.request_id, resource_kind: 'learning_space', resource_id: scope });
      let receipt;
      for (let attempt = 0; attempt < 170; attempt++) {
        const response = await page.request.get(api + '/requests/receipt?' + query, { headers });
        assert.ok(response.ok(), await response.text());
        receipt = await response.json();
        if (receipt.receipt_state === 'completed') break;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      assert.equal(receipt?.result?.outcome, 'completed', JSON.stringify(receipt));
      return receipt.result;
    }

    const first = await send('请讲解一个量增加四分之一，我不懂增加量和新量的区别。');
    assert.equal(first.current.current_activity.type, 'explanation');
    const second = await send('我没懂，能换一种说法，区分原量和增加量吗？');
    assert.equal(second.current.current_activity.activity_ref.activity_id, first.current.current_activity.activity_ref.activity_id);
    await finish();

    const message = { owner: 'interaction', type: 'message', id: first.message_refs[0] };
    const report = {
      presentation_id: randomUUID(), surface: 'history', resource_ref: message,
      content_part_refs: [{ ...message, path: '/parts/0' }],
    };
    const received = await page.request.post(root + '/presentations', { headers, data: report });
    assert.equal(received.status(), 200, await received.text());
    const recorded = await received.json();
    const replay = await page.request.post(root + '/presentations', { headers, data: report });
    assert.equal(replay.status(), 200, await replay.text());
    assert.deepEqual(await replay.json(), recorded);
    const different = await page.request.post(root + '/presentations', { headers, data: { ...report, surface: 'chat' } });
    assert.equal(different.status(), 409, await different.text());

    await page.reload();
    await page.getByRole('button', { name: /E04 合成教材/ }).last().click();
    await page.getByLabel('输入消息').waitFor();
    await page.locator('#study-message-' + first.message_refs[0]).waitFor();
    await page.screenshot({ path: path.join(out, 'teaching-provision.png'), fullPage: true });
    await writeFile(path.join(out, 'provisions.json'), JSON.stringify({ scope, first, second, report, recorded }, null, 2));
    console.log('Verified confirmed replies without display reports, late display and idempotent replay.');
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });
