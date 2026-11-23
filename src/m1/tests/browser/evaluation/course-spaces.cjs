// Walk real course applications and their asynchronous goal results in the M1 K3s cluster.
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

async function run() {
  const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
  const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
  assert.ok(origin && evidence && process.env.M1_TEST_TARGET_FIXTURE);
  const fixture = JSON.parse(await readFile(process.env.M1_TEST_TARGET_FIXTURE, 'utf8'));
  const { textbook_id, import_id, chapter_refs } = fixture;
  let target = fixture.target;
  const root = origin + '/api/m1';
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  async function login(role, login, password) {
    assert.ok(login && password);
    const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } });
    await page.goto(origin + '/' + role + '/');
    await page.getByLabel('账号').fill(login);
    await page.getByLabel('密码').fill(password);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: /退出/ }).waitFor();
    const session = await (await page.request.get(root + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    return {
      page, account: session.account,
      async call(method, route, data, status = 200) {
        const response = await page.request.fetch(root + route, { method, headers, data });
        assert.equal(response.status(), status, await response.text());
        return response.json();
      },
    };
  }
  try {
    const admin = await login('admin', process.env.M1_TEST_DOMAIN_LOGIN, process.env.M1_TEST_DOMAIN_PASSWORD);
    const student = await login('student', process.env.M1_TEST_DOMAIN_STUDENT_LOGIN, process.env.M1_TEST_DOMAIN_STUDENT_PASSWORD);
    if (student.account.usage_gaps.length) {
      const consent = student.page.getByRole('button', { name: '我愿意参与测试' });
      await consent.click();
      await student.page.getByRole('heading', { name: '选择教材和目标' }).waitFor();
    }
    const read = route => admin.call('GET', route);
    const post = (route, body, status) => admin.call('POST', route, body, status);
    target = (await post('/learning-targets', {
      action: 'create', request_id: randomUUID(), textbook_id,
      title: '课程验收 ' + randomUUID().slice(0, 6),
      items: target.items.map(({ item_id, ...item }) => ({ ...item, method_mode: 'any_one' })),
    })).result.target;
    const target_id = target.target_ref.target_id;
    const contents = await read(`/material-imports/${import_id}/contents`);
    const chapters = contents.chapters.filter(row => chapter_refs.includes(row.chapter_id)).map(row => ({
      chapter_id: row.chapter_id, revision: row.revision,
      content_refs: contents.items.filter(item => item.validity === 'current' && item.chapter_ref.id === row.chapter_id)
        .map(item => ({ owner: 'product', type: 'material_candidate', id: item.candidate_id, revision: item.candidate_revision })),
    }));
    const activity_config_refs = await Promise.all(['explanation', 'question_answer', 'detection', 'free_chat'].map(async type =>
      (await read('/interaction/activity-configs/' + type)).config_ref));
    const head = async () => (await read('/course-applications/current?' + new URLSearchParams({ textbook_id, target_id }))).application_ref;
    const inspect = async () => post('/course-applications/checks', {
      request_id: randomUUID(), textbook_id, target_ref: target.target_ref,
      expected_application_ref: await head(), chapters, activity_config_refs,
    });
    async function confirm(check, status) {
      return post('/course-applications/confirmations', {
        request_id: randomUUID(), check_ref: check.check_ref,
        expected_application_ref: check.base_application_ref,
      }, status);
    }
    async function revise(title, method_mode) {
      const result = await post('/learning-targets', {
        request_id: randomUUID(), action: 'update', textbook_id, target_id,
        expected_revision: target.target_ref.revision, title,
        items: target.items.map(item => ({ ...item, method_mode })),
      });
      target = result.result.target;
    }
    const nav = admin.page.getByRole('navigation', { name: '管理功能' });
    await nav.getByRole('button', { name: '目标管理' }).click();
    const targetArea = admin.page.getByRole('region', { name: '目标管理' });
    await targetArea.getByLabel('教材').selectOption(textbook_id);
    await targetArea.getByRole('button', { name: target.title + ' · v1' }).click();
    const uiCheck = admin.page.waitForResponse(response =>
      response.url().endsWith('/api/m1/course-applications/checks') && response.ok());
    await targetArea.getByRole('button', { name: '检查课程' }).click();
    const first = (await (await uiCheck).json()).result;
    await targetArea.getByRole('button', { name: '确认应用' }).waitFor();
    await admin.page.screenshot({ path: path.join(evidence, 'course-check.png'), fullPage: true });
    assert.equal(first.can_apply, true);
    assert.ok(first.readiness.some(row => row.purpose === 'evaluation' && row.status === 'limited'));
    assert.deepEqual(await head(), first.base_application_ref);
    if (!first.base_application_ref) {
      const preliminary = await student.call('GET', '/course-options');
      assert.ok(!preliminary.items.some(item => item.target_ref.target_id === target_id));
    }
    await revise('四分之一课程 ' + randomUUID().slice(0, 6), 'any_one');
    const old = await confirm(first, 409);
    assert.equal(old.error.code, 'check_stale');
    const applied = (await confirm((await inspect()).result)).result;
    const options = await student.call('GET', '/course-options');
    assert.ok(options.items.some(item => item.target_ref.target_id === target_id));
    const request = {
      request_id: randomUUID(), action: 'create', textbook_id, target_id,
      expected_application_ref: applied.application_ref,
    };
    const opened = await student.call('POST', '/learning-spaces/open', request);
    const space = opened.result.space.space_id;
    assert.deepEqual(await student.call('POST', '/learning-spaces/open', request), opened);
    const repeated = await student.call('POST', '/learning-spaces/open', { ...request, request_id: randomUUID() });
    assert.equal(repeated.result.space.space_id, space);
    assert.equal(repeated.result.created, false);
    assert.notEqual(repeated.result.entry_event_ref, opened.result.entry_event_ref);
    const forbidden = await student.call('GET', '/learning-spaces?student_id=' + randomUUID(), null, 404);
    assert.equal(forbidden.error.code, 'not_found');
    const resultUrl = `/learning-spaces/${space}/goal`;
    async function result() {
      for (let attempt = 0; attempt < 35; attempt++) {
        const value = await read(resultUrl);
        if (!value.pending) return value;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      throw new Error('K3s goal calculation did not become ready');
    }
    const initial = await result();
    assert.equal(initial.current.result.attainment, null);
    assert.equal(initial.current.result.readiness, 'unprepared');
    await revise('四分之一课程改名 ' + randomUUID().slice(0, 6), 'any_one');
    const nameOnly = (await confirm((await inspect()).result)).result;
    assert.deepEqual(nameOnly.affected_spaces, [space]);
    const unchanged = await result();
    assert.deepEqual(unchanged.target_basis_ref, initial.target_basis_ref);
    assert.equal(unchanged.current.goal_evaluation_id, initial.current.goal_evaluation_id);
    await revise('四分之一课程逐法达标 ' + randomUUID().slice(0, 6), 'each');
    const methodChanged = (await confirm((await inspect()).result)).result;
    assert.deepEqual(methodChanged.affected_spaces, [space]);
    const updated = await result();
    assert.notEqual(updated.current.goal_evaluation_id, initial.current.goal_evaluation_id);
    assert.notEqual(updated.target_basis_ref.id, initial.target_basis_ref.id);
    assert.equal(updated.current.result.items[0].method_mode, 'each');
    const noChange = (await confirm((await inspect()).result)).result;
    assert.equal(noChange.changed, false);
    assert.deepEqual(noChange.application_ref, methodChanged.application_ref);
    const events = (await read(`/learning-spaces/${space}/events?limit=100`)).items;
    assert.equal(events.filter(item => item.event_type === 'LearningTargetApplied').length, 2);
    assert.equal(events.filter(item => item.event_type === 'LearningSpaceAdoptionChanged').length, 2);
    const filtered = (await read(`/learning-spaces/${space}/events?event_type=GoalEvaluationCompleted`)).items;
    assert.equal(filtered.length, 2);
    const menu = admin.page.getByRole('navigation', { name: '管理功能' });
    await menu.getByRole('button', { name: '学习空间', exact: true }).click();
    const workspace = admin.page.getByRole('region', { name: '学习空间' });
    await workspace.getByLabel('学生姓名').fill(student.account.display_name);
    await workspace.getByRole('button', { name: '搜索' }).click();
    await workspace.getByRole('row').filter({ hasText: target.title })
      .getByRole('button', { name: student.account.display_name }).click();
    const tabs = workspace.getByRole('navigation', { name: '空间详情' });
    await tabs.getByRole('button', { name: '学习目标' }).click();
    await workspace.getByRole('status').filter({ hasText: '准备不足' }).waitFor();
    await workspace.getByRole('heading', { name: /先求增加量/ }).waitFor();
    await workspace.getByRole('heading', { name: /先求新量倍数/ }).waitFor();
    await admin.page.screenshot({ path: path.join(evidence, 'space-goal.png'), fullPage: true });
    await tabs.getByRole('button', { name: '空间事件' }).click();
    await workspace.getByLabel('事件类型').selectOption('GoalEvaluationCompleted');
    await workspace.getByRole('row').filter({ hasText: '完成目标计算' }).first().waitFor();
    await admin.page.screenshot({ path: path.join(evidence, 'space-events.png'), fullPage: true });
    await tabs.getByRole('button', { name: '教材', exact: true }).click();
    const chaptersNav = workspace.getByRole('navigation', { name: '教材章节' });
    const readChapter = admin.page.waitForResponse(response =>
      response.url().includes(`/api/m1/learning-spaces/${space}/chapters/`) && response.ok());
    await chaptersNav.getByRole('button').first().click();
    await readChapter;
    await admin.page.screenshot({ path: path.join(evidence, 'space-material.png'), fullPage: true });
    await student.page.reload();
    await student.page.getByRole('button', { name: new RegExp(target.title) }).last().click();
    await student.page.getByRole('button', { name: '返回课程列表' }).waitFor();
    await student.page.screenshot({ path: path.join(evidence, 'student-adoption.png'), fullPage: true });
    await writeFile(path.join(evidence, 'course-space-chain.json'), JSON.stringify({
      space, initial, updated, events: events.map(({ event_id, scope_event_seq, event_type }) => ({ event_id, scope_event_seq, event_type })),
    }, null, 2));
    console.log('Verified check/apply, student entry deduplication, goal recalculation, and the three admin tabs.');
  } finally {
    await browser.close();
  }
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
