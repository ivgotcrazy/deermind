const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { enterCourse } = require('./select-course.cjs');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
const out = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const scenarios = [
  {
    name: '基础不足',
    introduction: '请讲解一个量增加四分之一，我不懂增加量和新量的区别。',
    question: '我还有一个独立问题：能插入一个答疑，解释为什么要加回原量，再回到当前讲解吗？',
  },
  {
    name: '会做但解释不足',
    introduction: '请讲解为什么 8 增加四分之一后等于 10。我会算，但是不能解释原因。',
    question: '请先插入一个答疑：为什么式子中有 1？答完再继续这段讲解。',
  },
  {
    name: '具备基础',
    introduction: '我知道原量和增加量的区别。请讲解如何把两步计算合写成原量乘以四分之五。',
    question: '请插入一个独立答疑：怎么检查 5/4 和 4/5 哪个合理？答完回到原来的讲解。',
  },
];

async function run() {
  await mkdir(out, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({
      viewport: { width: 1360, height: 960 },
      recordVideo: { dir: out, size: { width: 1360, height: 960 } },
    });
    await page.goto(origin + '/student/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_STUDENT_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_STUDENT_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: '退出登录' }).waitFor();
    const scope = await enterCourse(page, /E04 合成教材/);
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
    const wait = async (request, action) => {
      const query = new URLSearchParams({ action, request_id: request, resource_kind: 'learning_space', resource_id: scope });
      let receipt;
      for (let attempt = 0; attempt < 245; attempt++) {
        const response = await page.request.get(api + '/requests/receipt?' + query, { headers });
        assert.ok(response.ok(), await response.text());
        receipt = await response.json();
        if (receipt.receipt_state === 'completed') return receipt;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      throw new Error('Learning work did not finish: ' + JSON.stringify(receipt));
    };
    async function turn(wording, afterAcceptance = async () => {}) {
      await chat.getByLabel('输入消息').fill(wording);
      const sent = page.waitForResponse(response => response.url() === root + '/inputs' && response.status() === 202);
      await chat.getByRole('button', { name: '发送', exact: true }).click();
      const command = (await sent).request().postDataJSON();
      await afterAcceptance();
      return await wait(command.request_id, 'interaction.handle_input');
    }

    let state = await current();
    while (state.current_activity) state = await control('结束活动');
    const results = [];
    for (const [index, scenario] of scenarios.entries()) {
      const initial = await turn(scenario.introduction);
      assert.equal(initial.result?.outcome, 'completed', JSON.stringify(initial));
      const lesson = initial.result.current.current_activity;
      assert.equal(lesson.type, 'explanation');
      const followup = await turn(scenario.question);
      assert.equal(followup.result?.outcome, 'completed', JSON.stringify(followup));
      assert.equal(followup.result.current.current_activity.parent_id, lesson.activity_ref.activity_id);
      assert.equal((await control('结束活动')).current_activity.activity_ref.activity_id, lesson.activity_ref.activity_id);
      await chat.getByRole('button', { name: '准备检测', exact: true }).click();
      const confirm = chat.getByRole('button', { name: '确认并开始', exact: true }).last();
      await confirm.waitFor({ timeout: 220_000 });
      assert.equal((await current()).current_round, null);
      const testing = await control('确认并开始');
      assert.equal(testing.current_round.state, 'open');

      const refreshes = [];
      const watchRefresh = request => refreshes.push({
        path: new URL(request.url()).pathname, method: request.method(),
      });
      page.on('request', watchRefresh);
      await page.reload();
      await chat.getByLabel('你的作答').waitFor();
      page.off('request', watchRefresh);
      assert.ok(refreshes.some(item => item.method === 'GET' && item.path === '/api/m1/learning-spaces/' + scope + '/workspace'));
      assert.ok(!refreshes.some(item => item.method === 'POST' && item.path === '/api/m1/learning-spaces/open'));
      assert.equal((await current()).current_round.round_ref.id, testing.current_round.round_ref.id);
      let raceResult;
      const help = await turn('请给这一题一点提示，我不知道第一步怎么算。', async () => {
        if (index !== 0) return;
        const round = testing.current_round;
        const raced = await page.request.post(root + '/answers', { headers, data: {
          request_id: randomUUID(), submission_id: randomUUID(), answer: { text: '0' },
          activity_ref: testing.current_activity.activity_ref, task_use_ref: round.task_use_ref,
          round_ref: round.round_ref, expected_round_revision: round.round_ref.revision,
        } });
        assert.equal(raced.status(), 409, await raced.text());
        raceResult = (await raced.json()).error.code;
        assert.ok(['interaction_busy', 'round_closed'].includes(raceResult));
      });
      assert.equal(help.result?.outcome, 'completed', JSON.stringify(help));
      assert.equal(help.result.current.current_activity.parent_id, testing.current_activity.activity_ref.activity_id);
      const closed = await control('结束活动');
      assert.equal(closed.current_round.state, 'closed');
      assert.equal(closed.current_round.can_continue, false);
      await control('结束活动');
      await control('结束活动');
      assert.equal(await chat.getByText(/已掌握|未掌握|掌握概率/).count(), 0);
      results.push({ scenario: scenario.name, initial, followup, testing, help, raceResult, closed });
      await page.screenshot({ path: path.join(out, 'quarter-case-' + (index + 1) + '.png'), fullPage: true });
      await writeFile(path.join(out, 'quarter-learning-path.json'), JSON.stringify({ scope, results }, null, 2));
    }
    console.log('Verified all three quarter-learning paths on the existing K3s cluster.');
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });
