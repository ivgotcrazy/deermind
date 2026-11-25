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
  const { textbook_id, import_id } = fixture;
  let target = fixture.target;
  const root = origin + '/api/m1';
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  async function login(role, login, password) {
    assert.ok(login && password);
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(origin + '/' + role + '/');
    await page.getByLabel('账号').fill(login);
    await page.getByLabel('密码', { exact: true }).fill(password);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: /退出/ }).waitFor();
    const session = await (await page.request.get(root + '/auth/session')).json();
    const headers = {
      Origin: origin,
      'X-Expected-Session': session.session_id,
      'X-CSRF-Token': session.csrf_token,
    };
    return {
      page,
      account: session.account,
      async call(method, route, data, status = 200) {
        const response = await page.request.fetch(root + route, { method, headers, data });
        assert.equal(response.status(), status, await response.text());
        return response.json();
      },
    };
  }
  try {
    const admin = await login(
      'admin',
      process.env.M1_TEST_DOMAIN_LOGIN,
      process.env.M1_TEST_DOMAIN_PASSWORD,
    );
    const student = await login(
      'student',
      process.env.M1_TEST_DOMAIN_STUDENT_LOGIN,
      process.env.M1_TEST_DOMAIN_STUDENT_PASSWORD,
    );
    if (student.account.usage_gaps.length) {
      const consent = student.page.getByRole('button', { name: '我愿意参与测试' });
      await consent.click();
      await student.page.getByRole('heading', { name: '选择教材和目标' }).waitFor();
    }
    const read = (route) => admin.call('GET', route);
    const domainId = (await read('/textbooks/' + textbook_id)).import.textbook.domain_id;
    const post = (route, body, status) => admin.call('POST', route, body, status);
    target = (await read('/learning-targets/' + target.target_ref.target_id)).target;
    const chapterRefs = new Set(
      fixture.chapter_refs ?? target.items.flatMap((item) => item.chapter_refs),
    );
    target = (
      await post('/learning-targets', {
        action: 'create',
        request_id: randomUUID(),
        textbook_id,
        title: '课程验收 ' + randomUUID().slice(0, 6),
        items: target.items.map(({ item_id, ...item }) => ({ ...item, method_mode: 'any_one' })),
      })
    ).result.target;
    const target_id = target.target_ref.target_id;
    const contents = await read(`/material-imports/${import_id}/contents`);
    const chapters = contents.chapters
      .filter((row) => chapterRefs.has(row.chapter_id))
      .map((row) => ({
        chapter_id: row.chapter_id,
        revision: row.revision,
        content_refs: contents.items
          .filter((item) => item.validity === 'current' && item.chapter_ref?.id === row.chapter_id)
          .map((item) => ({
            owner: 'product',
            type: 'material_candidate',
            id: item.candidate_id,
            revision: item.candidate_revision,
          })),
      }));
    const activity_config_refs = await Promise.all(
      ['explanation', 'question_answer', 'detection', 'free_chat'].map(
        async (type) => (await read('/interaction/activity-configs/' + type)).config_ref,
      ),
    );
    const head = async () =>
      (
        await read(
          '/course-applications/current?' + new URLSearchParams({ textbook_id, target_id }),
        )
      ).application_ref;
    const inspect = async () =>
      post('/course-applications/checks', {
        request_id: randomUUID(),
        textbook_id,
        target_ref: target.target_ref,
        expected_application_ref: await head(),
        chapters,
        activity_config_refs,
      });
    async function confirm(check, status) {
      return post(
        '/course-applications/confirmations',
        {
          request_id: randomUUID(),
          check_ref: check.check_ref,
          expected_application_ref: check.base_application_ref,
        },
        status,
      );
    }
    async function revise(title, method_mode) {
      const result = await post('/learning-targets', {
        request_id: randomUUID(),
        action: 'update',
        textbook_id,
        target_id,
        expected_revision: target.target_ref.revision,
        title,
        items: target.items.map((item) => ({ ...item, method_mode })),
      });
      target = result.result.target;
    }
    const nav = admin.page.getByRole('navigation', { name: '管理功能' });
    const targetArea = admin.page.getByRole('region', { name: '目标管理' });
    async function showApplication() {
      await nav.getByRole('button', { name: '目标管理' }).click();
      await targetArea.getByLabel('领域', { exact: true }).selectOption(domainId);
      await targetArea.getByLabel('教材').selectOption(textbook_id);
      await targetArea
        .getByRole('button', {
          name: target.title + ' · v' + target.target_ref.revision,
          exact: true,
        })
        .click();
      await admin.page.waitForFunction(
        (title) =>
          document.querySelector('section[aria-label="目标管理"] form input[required]')?.value ===
          title,
        target.title,
      );
      await targetArea.getByRole('tab', { name: '检查与应用' }).click();
    }
    await showApplication();
    const [uiCheck] = await Promise.all([
      admin.page.waitForResponse(
        (response) => response.url().endsWith('/api/m1/course-applications/checks'),
        { timeout: 10_000 },
      ),
      targetArea.getByRole('button', { name: '检查课程' }).click(),
    ]).catch(async (error) => {
      await admin.page.screenshot({ path: path.join(evidence, 'check-error.png') });
      const alerts = await targetArea.getByRole('alert').allTextContents();
      throw new Error(`课程检查未完成。页面提示 ${alerts.join(' ')}`, { cause: error });
    });
    assert.ok(uiCheck.ok(), await uiCheck.text());
    const first = (await uiCheck.json()).result;
    await targetArea.getByRole('button', { name: '确认应用' }).waitFor();
    await admin.page.screenshot({ path: path.join(evidence, 'course-check.png'), fullPage: true });
    assert.equal(first.can_apply, true);
    assert.ok(first.readiness.some((row) => row.purpose === 'evaluation'));
    assert.deepEqual(await head(), first.base_application_ref);
    if (!first.base_application_ref) {
      const preliminary = await student.call('GET', '/course-options');
      assert.ok(!preliminary.items.some((item) => item.target_ref.target_id === target_id));
    }
    await revise('四分之一课程 ' + randomUUID().slice(0, 6), 'any_one');
    const old = await confirm(first, 409);
    assert.equal(old.error.code, 'check_stale');
    const applied = (await confirm((await inspect()).result)).result;
    const options = await student.call('GET', '/course-options');
    assert.ok(options.items.some((item) => item.target_ref.target_id === target_id));
    const request = {
      request_id: randomUUID(),
      action: 'create',
      textbook_id,
      target_id,
      expected_application_ref: applied.application_ref,
    };
    const opened = await student.call('POST', '/learning-spaces/open', request);
    assert.ok(opened.result.study_methods.length > 0);
    const space = opened.result.space.space_id;
    assert.deepEqual(await student.call('POST', '/learning-spaces/open', request), opened);
    const repeated = await student.call('POST', '/learning-spaces/open', {
      ...request,
      request_id: randomUUID(),
    });
    assert.equal(repeated.result.space.space_id, space);
    assert.equal(repeated.result.created, false);
    assert.notEqual(repeated.result.entry_event_ref, opened.result.entry_event_ref);
    const forbidden = await student.call(
      'GET',
      '/learning-spaces?student_id=' + randomUUID(),
      null,
      404,
    );
    assert.equal(forbidden.error.code, 'not_found');
    const resultUrl = `/learning-spaces/${space}/goal`;
    async function result() {
      for (let attempt = 0; attempt < 35; attempt++) {
        const value = await read(resultUrl);
        if (!value.pending) return value;
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      throw new Error('K3s goal calculation did not become ready');
    }
    const initial = await result();
    assert.equal(initial.current.result.attainment, null);
    await revise(target.title, 'each');
    await admin.page.reload();
    await showApplication();
    await targetArea.getByText('课程 v1 · 目标 v2', { exact: true }).waitFor();
    await targetArea.getByText('课程 v2 · 目标 v3', { exact: true }).waitFor();
    assert.equal(await targetArea.getByLabel('教材', { exact: true }).count(), 0);
    await admin.page.screenshot({ path: path.join(evidence, 'A00.png'), animations: 'disabled' });
    await targetArea.getByRole('button', { name: '检查课程', exact: true }).click();
    const confirmApplication = targetArea.getByRole('button', { name: '确认应用', exact: true });
    await confirmApplication.waitFor();
    await targetArea.getByRole('columnheader', { name: '学生可做什么' }).waitFor();
    await admin.page.screenshot({ path: path.join(evidence, 'A01.png'), animations: 'disabled' });
    await confirmApplication.click();
    const dialog = admin.page.getByRole('dialog', { name: '确认应用课程 v2', exact: true });
    await dialog.getByText('原学习记录保留', { exact: false }).waitFor();
    await admin.page.screenshot({
      path: path.join(evidence, 'A02.png'),
      animations: 'disabled',
    });
    await dialog.getByRole('button', { name: '取消', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' });
    assert.deepEqual(await head(), applied.application_ref);
    await confirmApplication.click();
    // The POST really commits before the lost response forces a receipt lookup.
    await admin.page.route(
      '**/api/m1/course-applications/confirmations',
      async (route) => {
        await route.fetch();
        await route.abort('failed');
      },
      { times: 1 },
    );
    await dialog.getByRole('button', { name: '确认应用', exact: true }).click();
    await dialog.getByRole('button', { name: '查询本次结果' }).click();
    await targetArea.getByText('已发布课程 v2', { exact: false }).waitFor();
    await targetArea.getByText('之前的课程', { exact: true }).waitFor();
    await targetArea.getByRole('columnheader', { name: '学生可做什么' }).waitFor();
    await admin.page.screenshot({ path: path.join(evidence, 'A03.png'), animations: 'disabled' });
    const latestApplication = await head();
    assert.notDeepEqual(latestApplication, applied.application_ref);
    const unchanged = await result();
    assert.deepEqual(unchanged.target_basis_ref, initial.target_basis_ref);
    assert.equal(unchanged.current.goal_evaluation_id, initial.current.goal_evaluation_id);

    await student.page.goto(origin + '/student/?space=' + space);
    const switcher = student.page.getByRole('button', { name: '切换学习空间' });
    await switcher.click();
    const picker = student.page.getByRole('dialog', { name: '切换学习空间' });
    await picker
      .getByRole('button', {
        name: '创建空间 ' + target.title + ' 课程 v2',
        exact: true,
      })
      .waitFor();
    await student.page.screenshot({
      path: path.join(evidence, 'student-version-picker.png'),
      animations: 'disabled',
    });
    await student.page.route(
      '**/api/m1/learning-spaces/open',
      async (route) => {
        await route.fetch();
        await route.abort('failed');
      },
      { times: 1 },
    );
    await picker
      .getByRole('button', {
        name: '创建空间 ' + target.title + ' 课程 v2',
        exact: true,
      })
      .click();
    await picker.getByRole('button', { name: '查询本次结果' }).click();
    await picker.waitFor({ state: 'hidden' });
    await switcher.getByText('v2', { exact: true }).waitFor();
    const newerSpace = new URL(student.page.url()).searchParams.get('space');
    assert.ok(newerSpace && newerSpace !== space);
    const fromSameVersion = (
      await student.call('POST', '/learning-spaces/open', {
        ...request,
        request_id: randomUUID(),
        expected_application_ref: latestApplication,
      })
    ).result;
    assert.equal(fromSameVersion.space.space_id, newerSpace);
    assert.equal(fromSameVersion.created, false);
    await student.page.screenshot({ path: path.join(evidence, 'student-v2.png') });

    await switcher.click();
    await picker
      .getByRole('button', {
        name: '进入空间 ' + target.title + ' 课程 v1',
        exact: true,
      })
      .click();
    await switcher.getByText('v1', { exact: true }).waitFor();
    assert.equal(new URL(student.page.url()).searchParams.get('space'), space);
    await student.page.goto(origin + '/student/');
    await switcher.getByText('v1', { exact: true }).waitFor();
    assert.equal(new URL(student.page.url()).searchParams.get('space'), space);
    const oldWorkspace = await student.call('GET', `/learning-spaces/${space}/workspace`);
    assert.deepEqual(oldWorkspace.adoption, opened.result.adoption);

    const noChange = (await confirm((await inspect()).result)).result;
    assert.equal(noChange.changed, false);
    assert.deepEqual(noChange.application_ref, latestApplication);
    const list = (await student.call('GET', '/learning-spaces?target_id=' + target_id)).items;
    assert.deepEqual(list.map((row) => row.application_version).sort(), [1, 2]);
    const events = (await read(`/learning-spaces/${space}/events?limit=100`)).items;
    assert.equal(events.filter((item) => item.event_type === 'LearningTargetApplied').length, 1);
    assert.equal(
      events.filter((item) => item.event_type === 'LearningSpaceAdoptionChanged').length,
      0,
    );
    const otherEvents = (await read(`/learning-spaces/${newerSpace}/events?limit=100`)).items;
    assert.equal(
      otherEvents.filter((item) => item.event_type === 'LearningTargetApplied').length,
      1,
    );
    await writeFile(
      path.join(evidence, 'course-space-chain.json'),
      JSON.stringify(
        {
          course: [applied.application_ref.id, latestApplication.id],
          spaces: [space, newerSpace],
          originalGoal: initial.current.goal_evaluation_id,
          restored: space,
          publicationReceipt: true,
          spaceEntryReceipt: true,
        },
        null,
        2,
      ),
    );
    console.log(
      'Verified versioned publication, two independent spaces and lost response recovery.',
    );
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
