const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { enterCourse } = require('./select-course.cjs');

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
    const scope = await enterCourse(page, /E04 合成教材/);
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const root = origin + '/api/m1/learning-spaces/' + scope;
    async function current() {
      const response = await page.request.get(root + '/conversation?view=current', { headers });
      assert.ok(response.ok(), await response.text());
      return (await response.json()).current;
    }
    async function finish() {
      const returned = page.waitForResponse(item => item.url() === root + '/activity-actions' && item.request().method() === 'POST');
      await page.getByRole('button', { name: '结束活动', exact: true }).click();
      const response = await returned;
      assert.equal(response.status(), 200, await response.text());
      return (await response.json()).result.current;
    }
    let before = await current();
    while (before.current_activity && before.current_round?.state !== 'open') before = await finish();
    if (!before.current_round) {
      await page.getByRole('region', { name: '学习对话' })
        .getByRole('button', { name: '准备检测', exact: true }).click();
      const confirm = page.getByRole('button', { name: '确认并开始' }).last();
      await confirm.waitFor({ timeout: 200_000 });
      await confirm.click();
      await page.getByLabel('你的作答').waitFor();
      before = await current();
    }
    assert.equal(before.current_round.state, 'open');
    await page.getByLabel('输入消息').fill('请给这一题一点提示，我不知道第一步怎么算。');
    const accepted = page.waitForResponse(item => item.url() === root + '/inputs' && item.request().method() === 'POST');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    const response = await accepted;
    assert.equal(response.status(), 202, await response.text());
    const input = response.request().postDataJSON();
    const args = new URLSearchParams({ action: 'interaction.handle_input', request_id: input.request_id, resource_kind: 'learning_space', resource_id: scope });
    let receipt;
    for (let attempt = 0; attempt < 190; attempt++) {
      const polled = await page.request.get(origin + '/api/m1/requests/receipt?' + args, { headers });
      assert.ok(polled.ok(), await polled.text());
      receipt = await polled.json();
      if (receipt.receipt_state === 'completed') break;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    assert.equal(receipt?.result?.outcome, 'completed', JSON.stringify(receipt));
    const child = receipt.result.current.current_activity;
    assert.equal(child.parent_id, before.current_activity.activity_ref.activity_id);
    assert.ok(['question_answer', 'explanation'].includes(child.type));
    const stale = await page.request.post(root + '/answers', { headers, data: {
      request_id: randomUUID(), submission_id: randomUUID(), answer: { text: '0' },
      activity_ref: before.current_activity.activity_ref,
      round_ref: before.current_round.round_ref, expected_round_revision: before.current_round.round_ref.revision,
      task_use_ref: before.current_round.task_use_ref,
    } });
    assert.equal(stale.status(), 409, await stale.text());
    const after = await finish();
    assert.equal(after.current_activity.activity_ref.activity_id, child.parent_id);
    assert.equal(after.current_round.state, 'closed');
    assert.equal(after.current_round.round_ref.id, before.current_round.round_ref.id);
    assert.equal(after.current_round.can_continue, false);
    await page.screenshot({ path: path.join(out, 'detection-help.png'), fullPage: true });
    await writeFile(path.join(out, 'detection-help.json'), JSON.stringify({ scope, before, input, receipt, after }, null, 2));
    console.log('Verified closed round, child help and return without reopening the round.');
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });
