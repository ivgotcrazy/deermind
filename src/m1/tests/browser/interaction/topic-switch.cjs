// 在合成课程中核对换主题后的根活动、返回和教材浏览。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
const output = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const api = origin + '/api/m1';
const title = 'E04 专项复验';

async function login(browser, role, loginName, password) {
  const page = await browser.newPage({ viewport: { width: 1360, height: 960 } });
  await page.goto(origin + '/' + role + '/');
  await page.getByLabel('账号').fill(loginName);
  await page.getByLabel('密码').fill(password);
  await page.getByRole('button', { name: '登录' }).click();
  await page.getByRole('button', { name: '退出登录' }).waitFor();
  const session = await (await page.request.get(api + '/auth/session')).json();
  const headers = {
    Origin: origin,
    'X-Expected-Session': session.session_id,
    'X-CSRF-Token': session.csrf_token,
  };
  async function call(method, route, data) {
    const response = await page.request.fetch(api + route, { method, headers, data });
    assert.ok(response.ok(), method + ' ' + route + ' ' + (await response.text()));
    return await response.json();
  }
  return { page, call };
}

async function applyFixture(admin) {
  const fixture = JSON.parse(await readFile(process.env.M1_TEST_TOPIC_COURSE, 'utf8'));
  const textbook = fixture.book.textbook_id;
  const prior = (await admin.call('GET', '/learning-targets/' + fixture.target.target_id)).target;
  const target = (
    await admin.call('POST', '/learning-targets', {
      action: 'create',
      request_id: randomUUID(),
      textbook_id: textbook,
      title,
      items: prior.items.map(({ item_id, ...item }) => item),
    })
  ).result.target;
  const material = await admin.call(
    'GET',
    '/material-imports/' + fixture.book.import_id + '/contents',
  );
  const chapterIds = new Set(prior.items.flatMap((item) => item.chapter_refs));
  const chapters = material.chapters
    .filter((chapter) => chapterIds.has(chapter.chapter_id))
    .map((chapter) => ({
      chapter_id: chapter.chapter_id,
      revision: chapter.revision,
      content_refs: material.items
        .filter((item) => item.validity === 'current' && item.chapter_ref.id === chapter.chapter_id)
        .map((item) => ({
          owner: 'product',
          type: 'material_candidate',
          id: item.candidate_id,
          revision: item.candidate_revision,
        })),
    }));
  const route = '/interaction/activity-configs/explanation';
  const baseline = await admin.call('GET', route);
  const configured = structuredClone(baseline.definition.blueprint);
  configured.nodes.find((node) => node.node_id === 'talk').allowed_actions.push('switch');
  async function save(blueprint, current) {
    return (
      await admin.call('PUT', route, {
        request_id: randomUUID(),
        config_kind: 'blueprint',
        definition: blueprint,
        expected_revision: current.config_ref.revision,
        config_ref: current.definition.blueprint_ref,
      })
    ).result.config_ref;
  }
  const changed = !baseline.definition.blueprint.nodes
    .find((node) => node.node_id === 'talk')
    .allowed_actions.includes('switch');
  const explanation = changed ? await save(configured, baseline) : baseline.config_ref;
  try {
    const otherConfigs = await Promise.all(
      ['free_chat', 'question_answer', 'detection'].map(
        async (type) =>
          (await admin.call('GET', '/interaction/activity-configs/' + type)).config_ref,
      ),
    );
    const check = (
      await admin.call('POST', '/course-applications/checks', {
        request_id: randomUUID(),
        textbook_id: textbook,
        target_ref: target.target_ref,
        expected_application_ref: null,
        chapters,
        activity_config_refs: [explanation, ...otherConfigs],
      })
    ).result;
    assert.ok(check.can_apply, JSON.stringify(check));
    await admin.call('POST', '/course-applications/confirmations', {
      request_id: randomUUID(),
      check_ref: check.check_ref,
      expected_application_ref: check.base_application_ref,
    });
  } finally {
    if (changed) {
      const current = await admin.call('GET', route);
      assert.deepEqual(current.config_ref, explanation);
      await save(baseline.definition.blueprint, current);
    }
  }
}

async function run() {
  await mkdir(output, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    if (process.env.M1_TEST_TOPIC_MODE === 'setup') {
      const admin = await login(
        browser,
        'admin',
        process.env.M1_TEST_DOMAIN_LOGIN,
        process.env.M1_TEST_DOMAIN_PASSWORD,
      );
      await applyFixture(admin);
      await admin.page.close();
    }
    const { page, call } = await login(
      browser,
      'student',
      process.env.M1_TEST_DOMAIN_STUDENT_LOGIN,
      process.env.M1_TEST_DOMAIN_STUDENT_PASSWORD,
    );
    const course = page.getByRole('button', { name: new RegExp(title) }).first();
    const entry = page.waitForResponse(
      (response) => response.url().endsWith('/learning-spaces/open') && response.ok(),
    );
    await course.click();
    const scope = (await (await entry).json()).result.space.space_id;
    const space = '/learning-spaces/' + scope;
    const chat = page.getByRole('region', { name: '学习对话' });
    async function control(button) {
      const posted = page.waitForResponse(
        (response) =>
          response.url() === api + space + '/activity-actions' &&
          response.request().method() === 'POST',
      );
      await button.click();
      const response = await posted;
      assert.equal(response.status(), 200, await response.text());
      return (await response.json()).result.current;
    }
    let current = (await call('GET', space + '/conversation?view=current')).current;
    while (current.current_activity) {
      current = await control(chat.getByRole('button', { name: '结束活动', exact: true }));
    }
    async function turn(words) {
      await chat.getByLabel('输入消息').fill(words);
      const posted = page.waitForResponse(
        (response) => response.url() === api + space + '/inputs' && response.status() === 202,
      );
      await chat.getByRole('button', { name: '发送', exact: true }).click();
      const command = (await posted).request().postDataJSON();
      const query = new URLSearchParams({
        action: 'interaction.handle_input',
        resource_kind: 'learning_space',
        resource_id: scope,
        request_id: command.request_id,
      });
      let receipt;
      for (let index = 0; index < 150; index++) {
        receipt = await call('GET', '/requests/receipt?' + query);
        if (receipt.receipt_state === 'completed') break;
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      assert.equal(receipt?.result?.outcome, 'completed', JSON.stringify(receipt));
      await page.locator('#study-message-' + receipt.result.message_refs[0]).waitFor();
      return receipt;
    }
    const original = await turn('请讲解一个量增加四分之一。我不懂算出增加量后为什么还要加回原量。');
    const first = original.result.current.current_activity;
    assert.equal(first.type, 'explanation');
    const reader = page.getByRole('navigation', { name: '教材章节' });
    await reader.getByRole('button').first().click();
    assert.equal(
      (await call('GET', space + '/conversation?view=current')).current.current_activity
        .activity_ref.activity_id,
      first.activity_ref.activity_id,
    );
    const changed = await turn(
      '我现在明确要换一个新主题。请暂停刚才的讲解，另开一个独立讲解，讲长方形的面积为什么等于长乘宽。',
    );
    const next = changed.result.current.current_activity;
    assert.equal(changed.result.current.path.length, 1);
    assert.equal(next.parent_id, null);
    assert.notEqual(next.activity_ref.activity_id, first.activity_ref.activity_id);
    assert.match(next.name, /面积|长方形/);
    const roots = await call('GET', space + '/conversation?view=activity_tree');
    assert.equal(
      roots.items.find((item) => item.activity_ref.activity_id === first.activity_ref.activity_id)
        .run_state,
      'paused',
    );
    const paused = page
      .getByRole('complementary', { name: '活动目录' })
      .getByRole('listitem')
      .filter({ has: page.getByRole('button', { name: first.name, exact: true }) })
      .first();
    const resume = paused.getByRole('button', { name: '继续活动', exact: true });
    await resume.waitFor();
    assert.ok(await resume.isDisabled());
    assert.equal(await resume.evaluate((button) => getComputedStyle(button).cursor), 'not-allowed');
    await page.screenshot({ path: path.join(output, 'topic-switch.png'), fullPage: true });
    assert.equal(
      (await control(chat.getByRole('button', { name: '结束活动', exact: true }))).current_activity,
      null,
    );
    const resumed = await control(resume);
    assert.equal(resumed.current_activity.activity_ref.activity_id, first.activity_ref.activity_id);
    await writeFile(
      path.join(output, 'topic-switch.json'),
      JSON.stringify({ scope, original, changed, roots }, null, 2),
    );
    console.log(
      'Verified topic change to a new root, independent browsing and return to the paused lesson.',
    );
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
