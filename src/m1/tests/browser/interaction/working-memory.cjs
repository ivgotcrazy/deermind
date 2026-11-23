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
    const opened = page.waitForResponse(response => response.url().endsWith('/learning-spaces/open') && response.ok());
    await page.getByRole('button', { name: /E04 合成教材/ }).first().click();
    const scope = (await (await opened).json()).result.space.space_id;
    const api = origin + '/api/m1';
    const root = api + '/learning-spaces/' + scope;
    const session = await (await page.request.get(api + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };

    async function control(button) {
      const received = page.waitForResponse(response => response.url() === root + '/activity-actions' && response.request().method() === 'POST');
      await page.getByRole('button', { name: button, exact: true }).click();
      const response = await received;
      assert.equal(response.status(), 200, await response.text());
      return (await response.json()).result.current;
    }

    let current = (await (await page.request.get(root + '/conversation?view=current', { headers })).json()).current;
    while (current.current_activity) current = await control('结束活动');
    const reader = page.getByRole('navigation', { name: '教材章节' });
    await reader.getByRole('button').first().click();
    await page.getByRole('button', { name: '引用本节', exact: true }).waitFor();

    const rejected = await page.request.post(root + '/inputs', {
      headers, data: {
        request_id: randomUUID(), input: { text: '请解释这个引用。', attachment_refs: [],
          explicit_refs: [{ owner: 'product', type: 'chapter', id: randomUUID(), revision: 1 }] },
      },
    });
    assert.equal(rejected.status(), 404, await rejected.text());

    async function send(wording) {
      await page.getByLabel('输入消息').fill(wording);
      const received = page.waitForResponse(response => response.url() === root + '/inputs' && response.status() === 202);
      await page.getByRole('button', { name: '发送', exact: true }).click();
      const response = await received;
      const command = response.request().postDataJSON();
      const query = new URLSearchParams({ action: 'interaction.handle_input', request_id: command.request_id, resource_kind: 'learning_space', resource_id: scope });
      let receipt;
      for (let attempt = 0; attempt < 250; attempt++) {
        const poll = await page.request.get(api + '/requests/receipt?' + query, { headers });
        assert.ok(poll.ok(), await poll.text());
        receipt = await poll.json();
        if (receipt.receipt_state === 'completed') break;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      assert.equal(receipt?.result?.outcome, 'completed', JSON.stringify(receipt));
      const last = page.locator('#study-message-' + receipt.result.message_refs[0]);
      await last.waitFor();
      return { command, result: receipt.result, wording: await last.innerText() };
    }

    const turns = [];
    turns.push(await send('请讲解一个量增加四分之一，我不懂增加量和新量的区别。'));
    assert.equal(turns[0].command.input.explicit_refs.length, 0);
    await page.getByRole('button', { name: '引用此处', exact: true }).first().click();
    turns.push(await send('请参考我引用的教材，用更简单的话继续讲解增加量与原量。'));
    assert.equal(turns[1].command.input.explicit_refs.length, 1);
    assert.equal(turns[1].command.input.explicit_refs[0].type, 'material_candidate');
    const activity = turns[0].result.current.current_activity.activity_ref.activity_id;
    const paused = await control('暂停活动');
    assert.equal(paused.current_activity, null);
    const resumed = await control('继续活动');
    assert.equal(resumed.current_activity.activity_ref.activity_id, activity);
    for (const wording of [
      '我还没懂，请继续当前讲解，先用数 8 说明原量和增加量。',
      '请继续当前讲解。先用图说明这两部分，我更喜欢先看图。',
      '我还没懂，请继续用同一个例子解释为什么还要加回原量。',
      '请继续当前讲解，用两句区分原量、增加量和新量。',
      '请继续当前讲解，把之前的 8 和增加四分之一联起来说。',
    ]) {
      turns.push(await send(wording));
    }
    assert.ok(turns.every(turn => turn.result.current.current_activity.activity_ref.activity_id === activity));
    await page.screenshot({ path: path.join(out, 'working-memory.png'), fullPage: true });
    await writeFile(path.join(out, 'working-memory.json'), JSON.stringify({ scope, activity, turns }, null, 2));
    console.log('Verified scoped textbook citation and resumed long conversation in K3s.');
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });
