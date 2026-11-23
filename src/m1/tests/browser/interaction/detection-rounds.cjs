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
    const opened = page.waitForResponse(item => item.url().endsWith('/learning-spaces/open') && item.ok());
    await page.getByRole('button', { name: /E04 合成教材/ }).first().click();
    const scope = (await (await opened).json()).result.space.space_id;
    const received = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': received.session_id, 'X-CSRF-Token': received.csrf_token };
    const root = origin + '/api/m1/learning-spaces/' + scope;
    async function state() {
      const got = await page.request.get(root + '/conversation?view=current', { headers });
      assert.ok(got.ok(), await got.text());
      return (await got.json()).current;
    }
    let current = await state();
    while (current.current_activity) {
      assert.ok(!current.current_round);
      const acted = page.waitForResponse(item => item.url() === root + '/activity-actions' && item.request().method() === 'POST');
      await page.getByRole('button', { name: '结束活动', exact: true }).click();
      const ended = await acted;
      assert.equal(ended.status(), 200, await ended.text());
      current = (await ended.json()).result.current;
    }
    await page.getByRole('button', { name: '准备检测', exact: true }).click();
    const confirm = page.getByRole('button', { name: '确认并开始', exact: true }).last();
    await confirm.waitFor({ timeout: 200_000 });
    current = await state();
    assert.equal(current.current_round, null);

    const sent = page.waitForRequest(item => item.url() === root + '/activity-actions' && item.method() === 'POST');
    const accepted = page.waitForResponse(item => item.url() === root + '/activity-actions' && item.request().method() === 'POST');
    await confirm.click();
    const command = (await sent).postDataJSON();
    const result = await accepted;
    assert.equal(result.status(), 200, await result.text());
    const first = (await result.json()).result.current;
    assert.equal(first.current_round.state, 'open');
    assert.deepEqual(first.current_round.plan_ref, command.plan_ref);

    const again = await page.request.post(root + '/activity-actions', { headers, data: command });
    assert.equal(again.status(), 200, await again.text());
    assert.deepEqual((await again.json()).result.current.current_round, first.current_round);
    const bad = { ...command, request_id: randomUUID(), activity_ref: first.current_activity.activity_ref,
      expected_activity_revision: first.current_activity.activity_ref.revision };
    const stale = await page.request.post(root + '/activity-actions', { headers, data: {
      ...bad, plan_ref: { ...command.plan_ref, revision: command.plan_ref.revision + 1 },
    } });
    assert.equal(stale.status(), 409, await stale.text());
    const tooEarly = await page.request.post(root + '/activity-actions', { headers, data: {
      ...bad, request_id: randomUUID(), action: 'continue_detection',
    } });
    assert.equal(tooEarly.status(), 409, await tooEarly.text());
    assert.equal((await state()).current_round.round_ref.id, first.current_round.round_ref.id);

    await page.screenshot({ path: path.join(out, 'detection-round.png'), fullPage: true });
    await writeFile(path.join(out, 'detection-round.json'), JSON.stringify({ scope, command, first }, null, 2));
    console.log('Verified one confirmed round, original replay and early continuation rejection.');
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });
