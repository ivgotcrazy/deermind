const assert = require('node:assert/strict');
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
    const api = origin + '/api/m1/learning-spaces/' + scope;

    async function untilDone(action, request) {
      const query = new URLSearchParams({ action, resource_kind: 'learning_space', resource_id: scope, request_id: request });
      let receipt;
      for (let attempt = 0; attempt < 175; attempt++) {
        const got = await page.request.get(origin + '/api/m1/requests/receipt?' + query, { headers });
        assert.equal(got.status(), 200, await got.text());
        receipt = await got.json();
        if (receipt.receipt_state === 'completed') break;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      assert.equal(receipt?.receipt_state, 'completed', JSON.stringify(receipt));
      assert.equal(receipt.result.outcome, 'completed', JSON.stringify(receipt));
      return receipt;
    }

    async function ask(words, purpose) {
      await page.getByLabel('输入消息').fill(words);
      const accepted = page.waitForResponse(item => item.url() === api + '/inputs' && item.request().method() === 'POST');
      await page.getByRole('button', { name: '发送', exact: true }).click();
      const response = await accepted;
      assert.equal(response.status(), 202, await response.text());
      const receipt = await untilDone('interaction.handle_input', response.request().postDataJSON().request_id);
      const message = page.locator('#study-message-' + receipt.result.message_refs[0]);
      await message.waitFor({ timeout: 30_000 });
      const list = await page.request.get(api + '/conversation?view=messages&limit=20&after_seq=' + Math.max(0, receipt.result.current.latest_message_seq - 12), { headers });
      const stored = (await list.json()).items.find(item => item.message_id === receipt.result.message_refs[0]);
      const part = stored?.parts.find(item => item.type === 'question');
      assert.equal(part?.purpose, purpose);
      assert.equal(Boolean(part.worked_solution), purpose === 'example');
      return { receipt, part, message };
    }

    const example = await ask('继续当前讲解。请用课程里的任务给我一道例题，附上完整解法。', 'example');
    await example.message.getByText('查看解法', { exact: true }).click();
    const practice = await ask('继续当前讲解。请用课程里的任务给我一道练习，我先自己作答，请不要给出参考解法。', 'practice');
    assert.notEqual(practice.part.task_use_ref.id, example.part.task_use_ref.id);
    await practice.message.getByLabel('你的作答').fill('0');
    const response = page.waitForResponse(item => item.url() === api + '/answers' && item.request().method() === 'POST');
    await practice.message.getByRole('button', { name: '提交作答' }).click();
    const saved = await response;
    assert.equal(saved.status(), 200, await saved.text());
    const acceptance = await saved.json();
    assert.equal(acceptance.round_state, null);
    const answer = await untilDone('interaction.submit_answer', saved.request().postDataJSON().request_id);
    const feedback = page.locator('#study-message-' + answer.result.message_refs[0]);
    await feedback.waitFor({ timeout: 30_000 });
    await page.screenshot({ path: path.join(out, 'practice-feedback.png'), fullPage: true });
    await writeFile(path.join(out, 'teaching-questions.json'), JSON.stringify({ scope, example: example.part, practice: practice.part, acceptance, feedback: await feedback.innerText() }, null, 2));
    console.log('Verified example, practice answer and feedback with no detection round.');
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });
