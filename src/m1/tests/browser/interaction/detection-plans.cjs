const assert = require('node:assert/strict');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
const directory = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;

async function run() {
  await mkdir(directory, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1360, height: 960 } });
    await page.goto(origin + '/student/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_STUDENT_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_STUDENT_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: '退出登录' }).waitFor();
    const entered = page.waitForResponse(item => item.url().endsWith('/learning-spaces/open') && item.ok());
    await page.getByRole('button', { name: /E04 合成教材/ }).first().click();
    const scope = (await (await entered).json()).result.space.space_id;
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const api = origin + '/api/m1/learning-spaces/' + scope;

    async function verify(action, accepted) {
      assert.equal(accepted.status(), 202, await accepted.text());
      const initial = await accepted.json();
      const request = accepted.request().postDataJSON().request_id;
      const args = new URLSearchParams({ action, request_id: request, resource_kind: 'learning_space', resource_id: scope });
      let status;
      for (let attempt = 0; attempt < 205; attempt++) {
        const response = await page.request.get(origin + '/api/m1/requests/receipt?' + args, { headers });
        assert.ok(response.ok(), await response.text());
        status = await response.json();
        if (status.receipt_state === 'completed') break;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      assert.equal(status?.execution_ref, initial.execution_ref);
      assert.equal(status?.result?.outcome, 'completed', JSON.stringify(status));
      const message = page.locator('#study-message-' + status.result.message_refs[0]);
      await message.getByRole('region', { name: '检测题单' }).waitFor({ timeout: 30_000 });
      assert.equal(await message.getByLabel('你的作答').count(), 0);
      return { receipt: status, summary: await message.innerText() };
    }

    const initialView = await page.request.get(api + '/conversation?view=current', { headers });
    const initial = (await initialView.json()).current.current_activity;
    if (initial?.type === 'detection') {
      const restored = page.waitForResponse(item => item.url() === api + '/activity-actions' && item.request().method() === 'POST');
      await page.getByRole('button', { name: '结束活动', exact: true }).click();
      assert.equal((await restored).status(), 200);
    }
    const directRequest = page.waitForResponse(item => item.url() === api + '/detection-plans' && item.request().method() === 'POST');
    await page.getByRole('button', { name: '准备检测', exact: true }).click();
    const direct = await verify('interaction.prepare_detection', await directRequest);

    const ended = page.waitForResponse(item => item.url() === api + '/activity-actions' && item.request().method() === 'POST');
    await page.getByRole('button', { name: '结束活动', exact: true }).click();
    assert.equal((await ended).status(), 200);
    await page.getByLabel('输入消息').fill('我想做独立检测，请按当前学习目标先准备题单，给我确认。');
    const chatRequest = page.waitForResponse(item => item.url() === api + '/inputs' && item.request().method() === 'POST');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    const chat = await verify('interaction.handle_input', await chatRequest);
    await page.screenshot({ path: path.join(directory, 'detection-plans.png'), fullPage: true });
    await writeFile(path.join(directory, 'detection-plans.json'), JSON.stringify({ scope, direct, chat }, null, 2));
    console.log('Verified separate and chat detection preparation. Both require confirmation and preserve their original receipts.');
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });
