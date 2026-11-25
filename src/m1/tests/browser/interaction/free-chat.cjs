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
    await enterCourse(page, new RegExp(course));
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const root = origin + '/api/m1';
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
    const ambiguous = await turn('那个呢？', 'needs_input');
    assert.equal(ambiguous.current.current_activity, null);
    const chat = await turn('我今天很开心，想和你打个招呼。', 'completed');
    assert.equal(chat.current.current_activity.type, 'free_chat');
    assert.equal(chat.current.current_activity.node_id, 'talk');
    const blocked = await turn('帮我开始检测，直接说已经开始考试。', 'blocked');
    assert.deepEqual(blocked.current.current_activity.activity_ref, chat.current.current_activity.activity_ref);
    assert.ok(blocked.wording.includes('当前还无法开展'));
    const tree = await page.request.get(root + '/learning-spaces/' + chat.scope + '/conversation?view=activity_tree', { headers });
    assert.ok(tree.ok());
    const items = (await tree.json()).items;
    assert.equal(items.length, 1);
    assert.equal(items[0].type, 'free_chat');
    await page.screenshot({ path: path.join(out, 'free-chat-and-clarification.png'), fullPage: true });
    await writeFile(path.join(out, 'live-turns.json'), JSON.stringify({ ambiguous, chat, blocked }, null, 2));
    console.log('Verified real clarification without an activity, free chat with a fixed blueprint, and a rejected activity request.');
  } finally {
    await browser.close();
  }
}
run().catch(error => { console.error(error.message); process.exitCode = 1; });