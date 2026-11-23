const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
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
    await page.getByRole('button', { name: new RegExp(course) }).first().click();
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
    const first = await turn('请讲解一个量增加四分之一。原量20，为什么要加回原量？', 'completed');
    assert.equal(first.current.current_activity.type, 'explanation');
    assert.equal(first.current.current_activity.node_id, 'talk');
    assert.match(first.wording, /20/);
    const admin = await browser.newPage();
    await admin.goto(origin + '/admin/');
    await admin.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await admin.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await admin.getByRole('button', { name: '登录' }).click();
    await admin.getByRole('button', { name: '退出登录' }).waitFor();
    const adminSession = await (await admin.request.get(root + '/auth/session')).json();
    const adminHeaders = {
      Origin: origin,
      'X-Expected-Session': adminSession.session_id,
      'X-CSRF-Token': adminSession.csrf_token,
    };
    const configuration = root + '/interaction/activity-configs/explanation';
    const before = await admin.request.get(configuration, { headers: adminHeaders });
    assert.ok(before.ok());
    const fixed = await before.json();
    const rule = fixed.definition.rules[0];
    const modified = await admin.request.put(configuration, {
      headers: adminHeaders,
      data: {
        request_id: randomUUID(),
        config_kind: 'rule',
        config_ref: rule.ref,
        expected_revision: fixed.config_ref.revision,
        definition: { ...rule.definition, name: '合成验收规则修订 ' + randomUUID().slice(0, 6) },
      },
    });
    assert.ok(modified.ok(), await modified.text());
    const latest = (await modified.json()).result.config_ref;
    assert.notEqual(latest.id, fixed.config_ref.id);
    await admin.close();
    const second = await turn('我没懂，能换一种说法，区分原量和增加量吗？', 'completed');
    assert.equal(second.current.current_activity.activity_ref.activity_id,
      first.current.current_activity.activity_ref.activity_id);
    assert.match(second.wording, /增加量|原量/);
    const tree = await page.request.get(root + '/learning-spaces/' + first.scope + '/conversation?view=activity_tree', { headers });
    assert.ok(tree.ok());
    const roots = (await tree.json()).items;
    assert.ok(roots.some(item => item.type === 'explanation'));
    assert.ok(!roots.some(item => item.type === 'free_chat' && item.run_state === 'active'));
    await page.screenshot({ path: path.join(out, 'lesson.png'), fullPage: true });
    await writeFile(path.join(out, 'live-lesson.json'), JSON.stringify({ first, second, latest }, null, 2));
    console.log('Verified a real lesson, follow-up with the same activity, and handoff from free chat.');
  } finally {
    await browser.close();
  }
}
run().catch(error => { console.error(error.message); process.exitCode = 1; });
