const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
const out = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const mode = process.env.M1_TEST_FEEDBACK_MODE;

async function applyRecoveryCourse(browser) {
  const original = JSON.parse(
    await readFile('src/m1/.artifacts/e04-03-k3s-20261123/browser/course.json', 'utf8'),
  );
  const page = await browser.newPage();
  try {
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: '退出登录' }).waitFor();
    const api = origin + '/api/m1';
    const session = await (await page.request.get(api + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    async function call(method, route, data) {
      const response = await page.request.fetch(api + route, { method, headers, data });
      assert.ok(response.ok(), method + ' ' + route + ' ' + await response.text());
      return await response.json();
    }
    const textbook = original.book.textbook_id;
    const fixed = (await call('GET', '/learning-targets/' + original.target.target_id)).target;
    const item = fixed.items[0];
    const target = (await call('POST', '/learning-targets', {
      action: 'create', request_id: randomUUID(), textbook_id: textbook,
      title: 'E04 反馈恢复验收',
      items: [{
        title: item.title, claim_ref: item.claim_ref, chapter_refs: item.chapter_refs,
        method_mode: 'any_one', task_conditions: { description: '' },
        methods: [item.methods[0]],
      }],
    })).result.target;
    const material = await call('GET', '/material-imports/' + original.book.import_id + '/contents');
    const chapters = material.chapters.filter(chapter => item.chapter_refs.includes(chapter.chapter_id))
      .map(chapter => ({
        chapter_id: chapter.chapter_id, revision: chapter.revision,
        content_refs: material.items.filter(row => row.validity === 'current' && row.chapter_ref.id === chapter.chapter_id)
          .map(row => ({ owner: 'product', type: 'material_candidate', id: row.candidate_id, revision: row.candidate_revision })),
      }));
    const activity_config_refs = await Promise.all(
      ['free_chat', 'explanation', 'question_answer', 'detection'].map(async type =>
        (await call('GET', '/interaction/activity-configs/' + type)).config_ref),
    );
    const checked = (await call('POST', '/course-applications/checks', {
      request_id: randomUUID(), textbook_id: textbook, target_ref: target.target_ref,
      expected_application_ref: null, chapters, activity_config_refs,
    })).result;
    assert.equal(checked.can_apply, true);
    await call('POST', '/course-applications/confirmations', {
      request_id: randomUUID(), check_ref: checked.check_ref,
      expected_application_ref: checked.base_application_ref,
    });
  } finally {
    await page.close();
  }
}

async function run() {
  await mkdir(out, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    if (mode === 'setup') await applyRecoveryCourse(browser);
    const page = await browser.newPage({ viewport: { width: 1360, height: 960 } });
    await page.goto(origin + '/student/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_STUDENT_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_STUDENT_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: '退出登录' }).waitFor();
    const entered = page.waitForResponse(response => response.url().endsWith('/learning-spaces/open') && response.ok());
    await page.getByRole('button', { name: /E04 反馈恢复验收/ }).first().click();
    const scope = (await (await entered).json()).result.space.space_id;
    const api = origin + '/api/m1';
    const root = api + '/learning-spaces/' + scope;
    const session = await (await page.request.get(api + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const chat = page.getByRole('region', { name: '学习对话' });
    async function current() {
      const response = await page.request.get(root + '/conversation?view=current', { headers });
      assert.ok(response.ok(), await response.text());
      return (await response.json()).current;
    }
    async function control(button) {
      const changed = page.waitForResponse(response => response.url() === root + '/activity-actions' && response.request().method() === 'POST');
      await chat.getByRole('button', { name: button, exact: true }).last().click();
      const response = await changed;
      assert.equal(response.status(), 200, await response.text());
      return (await response.json()).result.current;
    }
    async function wait(request, acceptedState) {
      const query = new URLSearchParams({ action: 'interaction.submit_answer', request_id: request, resource_kind: 'learning_space', resource_id: scope });
      let receipt;
      for (let attempt = 0; attempt < 235; attempt++) {
        const response = await page.request.get(api + '/requests/receipt?' + query, { headers });
        assert.ok(response.ok(), await response.text());
        receipt = await response.json();
        if (receipt.receipt_state === 'completed' && receipt.business_state === acceptedState) return receipt;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      throw new Error('Feedback did not reach ' + acceptedState + ': ' + JSON.stringify(receipt));
    }
    async function submit(text) {
      await chat.getByLabel('你的作答').fill(text);
      const sent = page.waitForResponse(response => response.url() === root + '/answers' && response.request().method() === 'POST');
      await chat.getByRole('button', { name: '提交作答', exact: true }).click();
      const response = await sent;
      assert.equal(response.status(), 200, await response.text());
      const body = await response.json();
      assert.equal(body.round_state, 'closed');
      return { command: response.request().postDataJSON(), body };
    }
    async function startRound() {
      let state = await current();
      while (state.current_activity) state = await control('结束活动');
      await chat.getByRole('button', { name: '准备检测', exact: true }).click();
      await chat.getByRole('button', { name: '确认并开始', exact: true }).last().waitFor({ timeout: 210_000 });
      const opened = await control('确认并开始');
      assert.equal(opened.current_round.state, 'open');
    }
    async function calculation(before) {
      const response = await page.request.get(root + '/conversation?view=messages', { headers });
      assert.ok(response.ok(), await response.text());
      const question = (await response.json()).items.flatMap(item => item.parts)
        .find(part => part.type === 'question' && part.task_use_ref.id === before.current_round.task_use_ref.id);
      assert.ok(question, 'Final question must be formally available');
      const wording = JSON.stringify(question.statement);
      assert.match(wording, /四分之一|1\/4|\\frac\{1\}\{4\}|25%/);
      const original = wording.match(/(?<amount>\d+(?:\.\d+)?)\s*(?<unit>吨|米|人|本|件|箱|千克|袋|元|升|棵|支|道|个)/);
      assert.ok(original?.groups, wording);
      const amount = Number(original.groups.amount);
      return { amount, unit: original.groups.unit, increase: amount / 4, total: amount * 1.25 };
    }

    const failurePath = path.join(out, 'feedback-failure.json');
    if (mode === 'setup') {
      await startRound();
      console.log('Prepared and opened the final official round.');
    } else if (mode === 'failure') {
      const before = await current();
      assert.equal(before.current_round.state, 'open');
      const { total, unit } = await calculation(before);
      const accepted = await submit(String(total) + unit);
      const failed = await wait(accepted.command.request_id, 'failed');
      assert.equal(failed.result.current.current_round.state, 'closed');
      await writeFile(failurePath, JSON.stringify({ scope, accepted, failed }, null, 2));
      console.log('Saved the official answer before the forced model failure.');
    } else if (mode === 'correct') {
      await startRound();
      const round = await current();
      const { amount, unit, increase, total } = await calculation(round);
      const answer = `增加量是 ${amount} × 1/4 = ${increase}${unit}，它是原量的四分之一。` +
        `新量包含原量与增加量，所以是 ${amount} + ${increase} = ${total}${unit}。`;
      const accepted = await submit(answer);
      const completed = await wait(accepted.command.request_id, 'completed');
      await writeFile(path.join(out, 'correct-feedback.json'), JSON.stringify({ scope, accepted, completed }, null, 2));
      console.log('Verified formal feedback for a complete worked answer.');
    } else if (mode === 'post-answer-help') {
      const saved = JSON.parse(await readFile(path.join(out, 'feedback-recovered.json'), 'utf8'));
      const earlier = await current();
      assert.equal(earlier.current_round.state, 'closed');
      await chat.getByLabel('输入消息').fill('刚才已经交卷，请给一点提示，解释本题第一步。');
      const accepted = page.waitForResponse(response => response.url() === root + '/inputs' && response.status() === 202);
      await chat.getByRole('button', { name: '发送', exact: true }).click();
      const command = (await accepted).request().postDataJSON();
      const args = new URLSearchParams({ action: 'interaction.handle_input', request_id: command.request_id, resource_kind: 'learning_space', resource_id: scope });
      let result;
      for (let attempt = 0; attempt < 180; attempt++) {
        const got = await page.request.get(api + '/requests/receipt?' + args, { headers });
        assert.ok(got.ok(), await got.text());
        result = await got.json();
        if (result.receipt_state === 'completed') break;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      assert.equal(result?.business_state, 'completed', JSON.stringify(result));
      assert.equal(result.result.current.current_activity.parent_id, earlier.current_activity.activity_ref.activity_id);
      const restored = await control('结束活动');
      assert.deepEqual(restored.current_round, earlier.current_round);
      const original = await page.request.post(root + '/answers', { headers, data: saved.accepted.command });
      assert.equal(original.status(), 200, await original.text());
      assert.deepEqual(await original.json(), saved.accepted.body);
      await writeFile(path.join(out, 'help-after-submission.json'), JSON.stringify({ result, restored }, null, 2));
      console.log('Verified help after submission preserves the original answer and closed round.');
    } else {
      assert.equal(mode, 'recovery');
      const failure = JSON.parse(await readFile(failurePath, 'utf8'));
      const retry = { request_id: randomUUID(), execution_ref: failure.failed.execution_ref };
      const send = () => page.request.post(root + '/input-retries', { headers, data: retry });
      const resumed = await send();
      assert.equal(resumed.status(), 202, await resumed.text());
      const result = await resumed.json();
      assert.equal(result.execution_ref, failure.failed.execution_ref);
      assert.equal(result.input_id, failure.failed.result.input_id);
      const again = await send();
      assert.equal(again.status(), 202, await again.text());
      assert.deepEqual(await again.json(), result);
      const completed = await wait(failure.accepted.command.request_id, 'completed');
      assert.equal(completed.result.current.current_round.state, 'closed');
      const saved = await page.request.post(root + '/answers', { headers, data: failure.accepted.command });
      assert.equal(saved.status(), 200, await saved.text());
      assert.deepEqual(await saved.json(), failure.accepted.body);
      await page.reload();
      const displayed = page.locator('#study-message-' + completed.result.message_refs[0]);
      await displayed.waitFor();
      await writeFile(path.join(out, 'feedback-recovered.json'),
        JSON.stringify({ ...failure, retry, completed, wording: await displayed.innerText() }, null, 2));
      console.log('Recovered the original feedback and kept one original submission.');
    }
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });
