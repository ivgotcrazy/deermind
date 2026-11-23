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
    const root = origin + '/api/m1/learning-spaces/' + scope;
    async function answer(text) {
      await page.getByLabel('你的作答').fill(text);
      const response = page.waitForResponse(item => item.url() === root + '/answers' && item.request().method() === 'POST');
      await page.getByRole('button', { name: '提交作答', exact: true }).click();
      const saved = await response;
      assert.equal(saved.status(), 200, await saved.text());
      const body = await saved.json();
      assert.equal(body.round_state, 'closed');
      const original = saved.request().postDataJSON();
      const again = await page.request.post(root + '/answers', { headers, data: original });
      assert.equal(again.status(), 200, await again.text());
      assert.deepEqual(await again.json(), body);
      const duplicate = await page.request.post(root + '/answers', { headers, data: {
        ...original, request_id: randomUUID(), submission_id: randomUUID(),
      } });
      assert.equal(duplicate.status(), 409, await duplicate.text());
      assert.equal((await duplicate.json()).error.code, 'round_closed');
      const lookup = new URLSearchParams({ action: 'interaction.submit_answer', resource_kind: 'learning_space', resource_id: scope, request_id: original.request_id });
      let receipt;
      for (let attempt = 0; attempt < 110; attempt++) {
        const poll = await page.request.get(origin + '/api/m1/requests/receipt?' + lookup, { headers });
        assert.ok(poll.ok(), await poll.text());
        receipt = (await poll.json());
        if (receipt.receipt_state === 'completed') break;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      assert.equal(receipt?.result?.outcome, 'completed', JSON.stringify(receipt));
      const feedback = page.locator('#study-message-' + receipt.result.message_refs[0]);
      await feedback.waitFor({ timeout: 30_000 });
      return { body, feedback: await feedback.innerText(), current: receipt.result.current };
    }
    const first = await answer('0');
    let second = null;
    if (first.current.current_round.can_continue) {
      assert.match(first.feedback, /作答已保存/);
      await page.getByRole('button', { name: '继续下一题', exact: true }).click();
      second = await answer('0');
      assert.notEqual(first.current.current_round.round_ref.id, second.current.current_round.round_ref.id);
    }
    await page.screenshot({ path: path.join(out, 'detection-answer.png'), fullPage: true });
    await writeFile(path.join(out, 'detection-answer.json'), JSON.stringify({ scope, first, second }, null, 2));
    console.log('Verified official answer, immutable replay and no second answer for a closed round.');
  } finally {
    await browser.close();
  }
}
run().catch(error => { console.error(error.message); process.exitCode = 1; });
