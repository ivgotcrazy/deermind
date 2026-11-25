const assert = require('node:assert/strict');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { enterCourse } = require('./select-course.cjs');
const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
const out = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const course = process.env.M1_TEST_LEARNING_SPACE ?? 'E04 合成教材';
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
    const opened = await enterCourse(page, new RegExp(course));
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const root = origin + '/api/m1';
    async function current() {
      const response = await page.request.get(root + '/learning-spaces/' + opened + '/conversation?view=current', { headers });
      assert.ok(response.ok(), await response.text());
      return (await response.json()).current;
    }
    async function finish() {
      const save = page.waitForResponse(item => item.url().endsWith('/activity-actions') && item.request().method() === 'POST');
      await page.getByRole('button', { name: '结束活动', exact: true }).click();
      const response = await save;
      assert.equal(response.status(), 200, await response.text());
      return (await response.json()).result.current;
    }
    let starting = await current();
    while (starting.path.length > 1) starting = await finish();
    assert.equal(starting.current_activity.type, 'explanation');
    const input = page.getByLabel('输入消息');
    const send = page.getByRole('button', { name: '发送', exact: true });
    async function turn(words, expected) {
      const response = page.waitForResponse(item => item.url().endsWith('/inputs') && item.request().method() === 'POST');
      await input.fill(words);
      await send.click();
      const receiptResponse = await response;
      assert.equal(receiptResponse.status(), 202, await receiptResponse.text());
      const accepted = await receiptResponse.json();
      const command = receiptResponse.request().postDataJSON();
      const scope = new URL(receiptResponse.url()).pathname.split('/').at(-2);
      const query = new URLSearchParams({ action: 'interaction.handle_input', resource_kind: 'learning_space', resource_id: scope, request_id: command.request_id });
      let receipt;
      for (let attempt = 0; attempt < 130; attempt++) {
        const original = await page.request.get(root + '/requests/receipt?' + query, { headers });
        assert.equal(original.status(), 200, await original.text());
        receipt = await original.json();
        if (receipt.receipt_state === 'completed') break;
        await new Promise(resolve => setTimeout(resolve, 1200));
      }
      assert.equal(receipt?.receipt_state, 'completed', JSON.stringify(receipt));
      assert.equal(receipt.execution_ref, accepted.execution_ref);
      assert.equal(receipt.result.outcome, expected, JSON.stringify(receipt));
      assert.equal(receipt.result.message_refs.length, 1);
      const message = page.locator('#study-message-' + receipt.result.message_refs[0]);
      await message.waitFor({ timeout: 30_000 });
      return { scope, current: receipt.result.current, wording: await message.innerText() };
    }
    const answer = await turn(
      '请在当前讲解下面插入一个独立答疑。我的问题是：为什么四分之一是四个相等部分中的一个？',
      'completed',
    );
    assert.deepEqual(answer.current.path.map(item => item.type), ['explanation', 'question_answer']);
    const nested = await turn(
      '请继续留在这个答疑下面，先另开子讲解，讲讲什么叫单位一。讲完再回到这个答疑。',
      'completed',
    );
    assert.deepEqual(nested.current.path.map(item => item.type), [
      'explanation', 'question_answer', 'explanation',
    ]);
    assert.equal(nested.current.path[1].activity_ref.activity_id,
      answer.current.current_activity.activity_ref.activity_id);

    const returnToQuestion = await finish();
    assert.equal(returnToQuestion.current_activity.activity_ref.activity_id,
      answer.current.current_activity.activity_ref.activity_id);
    const returnToExplanation = await finish();
    assert.equal(returnToExplanation.current_activity.activity_ref.activity_id,
      answer.current.path[0].activity_ref.activity_id);
    const directory = page.getByRole('complementary', { name: '活动目录' });
    await directory.getByRole('button', { name: '展开' + answer.current.path[0].name }).click();
    await directory.getByRole('button', { name: '展开' + answer.current.current_activity.name }).last().click();
    await directory.getByRole('button', { name: nested.current.current_activity.name, exact: true }).click();
    await page.locator('#study-message-' + nested.current.current_activity.first_message_ref + '.selected').waitFor();
    await page.getByRole('region', { name: '学习对话' }).getByText(answer.current.path[0].name, { exact: true }).waitFor();
    await page.screenshot({ path: path.join(out, 'nested-activities.png'), fullPage: true });
    await writeFile(path.join(out, 'live-activity-paths.json'),
      JSON.stringify({ answer, nested, returnToQuestion, returnToExplanation }, null, 2));
    console.log('Verified explanation -> question -> nested explanation -> question -> original explanation, and read-only history navigation.');
  } finally {
    await browser.close();
  }
}
run().catch(error => { console.error(error.message); process.exitCode = 1; });
