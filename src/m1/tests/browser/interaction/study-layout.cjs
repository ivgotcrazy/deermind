// 在已部署的学生端验证布局。课程和章节响应使用固定夹具，登录走实际服务。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

async function closeReaderOnFocus(page, input) {
  const originalInput = await input.elementHandle();
  const close = page.getByRole('button', { name: '收起教材', exact: true });
  const bounds = await close.boundingBox();
  assert.ok(bounds);
  const sessionPath = '**/api/m1/auth/session';
  let release;
  const held = new Promise((resolve) => {
    release = resolve;
  });
  await page.route(
    sessionPath,
    async (route) => {
      const response = await route.fetch();
      await held;
      await route.fulfill({ response });
    },
    { times: 1 },
  );
  const requested = page.waitForRequest(sessionPath);
  const checked = page.waitForResponse(sessionPath);
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.evaluate(() => {
    document.addEventListener(
      'pointerdown',
      () => {
        window.dispatchEvent(new Event('focus'));
        document.dispatchEvent(new Event('visibilitychange'));
      },
      { once: true, capture: true },
    );
  });
  try {
    await page.mouse.down();
    await requested;
    await page.mouse.up();
    assert.equal(await originalInput.evaluate((node) => node.isConnected), true);
    await page.getByRole('button', { name: '展开教材', exact: true }).waitFor();
  } finally {
    release();
  }
  assert.equal((await checked).status(), 200);
  assert.equal(await originalInput.evaluate((node) => node.isConnected), true);
}

async function checkHeader(page, evidence, space) {
  const header = page.locator('.space-header');
  const switcher = header.getByRole('button', { name: '切换学习空间' });
  const account = header.getByRole('button', { name: '学生账号与退出登录' });
  const reader = header.getByRole('button', { name: '展开教材' });
  const picker = page.getByRole('dialog', { name: '切换学习空间' });

  const viewports = [[1360, 52], [390, 56], [320, 56]];
  for (const [width, expectedHeight] of viewports) {
    await page.setViewportSize({ width, height: 920 });
    const bar = await header.boundingBox();
    const anchor = await switcher.boundingBox();
    const tools = await account.boundingBox();
    const readerBox = await reader.boundingBox();
    assert.equal(bar.height, expectedHeight);
    assert.equal(bar.width, width);
    assert.ok(anchor.x + anchor.width <= readerBox.x && tools.x + tools.width <= width);
    assert.ok(Math.abs(anchor.y + anchor.height / 2 - (tools.y + tools.height / 2)) < 1);
    assert.equal(await switcher.getAttribute('title'), `${space.textbook_title} · ${space.target_title}`);
    if (width < 400) {
      const label = switcher.locator('.space-name');
      assert.ok(await label.evaluate((text) => text.scrollWidth > text.clientWidth));
    }

    await switcher.click();
    await picker.getByText(space.target_title, { exact: true }).waitFor();
    const panel = await picker.boundingBox();
    assert.equal(panel.y, expectedHeight + 6);
    if (width >= 1360) assert.ok(Math.abs(panel.x - anchor.x) <= 1);
    assert.ok(panel.x >= 0 && panel.x + panel.width <= width);
    await page.screenshot({ path: path.join(evidence, `space-picker-${width}.png`) });
    await page.keyboard.press('Escape');
    await picker.waitFor({ state: 'hidden' });
    assert.ok(await switcher.evaluate((control) => control === document.activeElement));
  }

  await account.click();
  await page.getByRole('button', { name: '退出登录', exact: true }).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '退出登录', exact: true }).waitFor({ state: 'hidden' });
  await reader.click();
  await page.getByRole('region', { name: '教材', exact: true }).waitFor();
  await page.screenshot({ path: path.join(evidence, 'navigation-320.png') });
}

async function run() {
  const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
  const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
  const login = process.env.M1_TEST_DOMAIN_STUDENT_LOGIN;
  const password = process.env.M1_TEST_DOMAIN_STUDENT_PASSWORD;
  assert.ok(origin && evidence && login && password);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1360, height: 920 } });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.name));
    await page.goto(origin + '/student/');
    await page.getByLabel('账号').fill(login);
    await page.getByLabel('密码', { exact: true }).fill(password);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: /退出登录/ }).waitFor();

    const chapters = ['原量与新量', '用两种方法解题'].map((title) => ({
      title, chapter_id: randomUUID(), revision: 1, page_refs: [], content_refs: [], associations: [],
    }));
    const targetTitle = '增加四分之一——说明原量、增加量和新量之间的关系，并用两种方法验证计算结果';
    const space = {
      space_id: randomUUID(), student_id: randomUUID(), student_name: '合成学生',
      textbook_id: randomUUID(), textbook_title: '分数学习样例', target_id: randomUUID(),
      target_title: targetTitle, target_revision: 1, application_version: 1,
      application_ref: { owner: 'product', type: 'course_application', id: randomUUID() },
      created_at: new Date().toISOString(),
    };
    const workspace = { space, adoption: { snapshot: { chapters } } };
    const withHistory = process.env.M1_TEST_ACTIVITY_FIXTURE === '1';
    const withTurn = process.env.M1_TEST_TURN_FIXTURE === '1';
    const work = { input: null, state: 'not_found', request: null, message: null };
    const activity = (name, kind, parent, state, hasChildren) => {
      const id = randomUUID();
      return {
        activity_ref: { activity_id: id, revision: 1 },
        type: kind, name, started_at: space.created_at, parent_id: parent ?? null,
        root_id: parent ?? id, node_id: 'start', run_state: state,
        first_message_ref: randomUUID(), has_children: hasChildren,
      };
    };
    const prior = activity('先前的讲解', 'explanation', null, 'completed', true);
    const child = activity('为什么加回原量', 'question_answer', prior.root_id, 'completed', false);
    const active = activity('当前讲解', 'explanation', null, 'active', false);
    if (withHistory || withTurn) {
      await page.route('**/api/m1/learning-spaces/*/conversation?*', (route) => {
        const query = new URL(route.request().url()).searchParams;
        if (query.get('view') === 'current') {
          return route.fulfill({ json: { current: {
            current_activity: active, path: [active],
            active_input_id: work.state === 'accepted' ? work.input : null,
            allowed_actions: work.state === 'accepted' ? [] : ['pause', 'finish'],
            latest_message_seq: work.message ? 3 : 2,
          } } });
        }
        if (query.get('view') === 'activity_tree') {
          const items = query.get('activity_ref') ? [child] : [active, prior];
          return route.fulfill({ json: { items, next_cursor: null } });
        }
        const items = [child, active].map((item, index) => ({
            message_id: item.first_message_ref, message_seq: index + 1, role: 'system',
            parts: [{ type: 'activity_notice', part_id: 'notice', text: '开始「' + item.name + '」。' }],
            activity_ref: item.activity_ref, committed_at: item.started_at,
        }));
        if (work.message) items.push(work.message);
        return route.fulfill({ json: {
          items, next_cursor: null, last_seq: items.length, upper_seq: items.length,
        } });
      });
    }
    if (withTurn) {
      await page.route('**/api/m1/learning-spaces/*/inputs', async (route) => {
        const submitted = route.request().postDataJSON();
        assert.equal(work.state, 'not_found');
        work.state = 'accepted';
        work.request = submitted.request_id;
        work.input = randomUUID();
        work.message = {
          message_id: randomUUID(), message_seq: 3, role: 'student', activity_ref: null,
          committed_at: space.created_at,
          parts: [{ type: 'text', part_id: 'text', text: submitted.input.text }],
        };
        await route.abort('connectionreset');
      });
      await page.route('**/api/m1/requests/receipt?*', (route) => {
        assert.equal(new URL(route.request().url()).searchParams.get('request_id'), work.request);
        return route.fulfill({ json: {
          receipt_state: work.state, business_state: work.state === 'completed' ? 'cancelled' : null,
        } });
      });
      await page.route('**/api/m1/learning-spaces/*/activity-actions', (route) => {
        const command = route.request().postDataJSON();
        assert.equal(command.action, 'stop_reply');
        assert.equal(command.target_input_id, work.input);
        work.state = 'completed';
        return route.fulfill({ json: { request_ref: randomUUID(), result: {
          outcome: 'stopped', committed_refs: [], current: {
            current_activity: active, path: [active], active_input_id: null,
            allowed_actions: ['pause', 'finish'], latest_message_seq: 3,
          },
        } } });
      });
    }
    const writes = [];
    page.on('request', (request) => {
      const route = new URL(request.url()).pathname;
      if (request.method() === 'POST' && /\/(inputs|activity-actions|learning-spaces\/open)$/.test(route)) {
        writes.push(route);
      }
    });
    await page.route('**/api/m1/course-options', (route) =>
      route.fulfill({ json: { items: [], next_cursor: null } }));
    await page.route('**/api/m1/learning-spaces', (route) =>
      route.fulfill({ json: { items: [space], next_cursor: null, recent_space_id: space.space_id } }));
    await page.route('**/api/m1/learning-spaces/open', (route) =>
      route.fulfill({ json: {
        request_ref: randomUUID(),
        result: { ...workspace, created: false, entry_event_ref: randomUUID() },
      } }));
    await page.route('**/api/m1/learning-spaces/*/workspace', (route) =>
      route.fulfill({ json: workspace }));
    await page.route('**/api/m1/learning-spaces/*/chapters/*', (route) => {
      const id = new URL(route.request().url()).pathname.split('/').at(-1);
      const chapter = chapters.find((entry) => entry.chapter_id === id);
      assert.ok(chapter);
      return route.fulfill({ json: { items: [{
        title: chapter.title + '（正文）',
        content: {
          schema_version: '1', role: 'definition', data_tables: [], source_refs: [],
          blocks: [{
            block_id: 'p-1', type: 'paragraph',
            provenance: { source_refs: [], transformation: 'generated' },
            payload: { spans: [{ type: 'text', text: '增加量等于原量乘增加比例。' }] },
          }],
        },
      }] } });
    });

    await page.reload();
    const consent = page.getByRole('button', { name: '我愿意参与测试' });
    await Promise.race([
      consent.waitFor(),
      page.getByRole('button', { name: '切换学习空间' }).waitFor(),
    ]);
    if (await consent.isVisible()) await consent.click();
    await page.getByRole('button', { name: '切换学习空间' }).waitFor();
    const reader = page.getByRole('navigation', { name: '教材章节' });
    const input = page.getByLabel('输入消息');
    await reader.waitFor();
    await input.waitFor();
    const inputBounds = await input.boundingBox();
    assert.ok(inputBounds && inputBounds.y + inputBounds.height <= 920);
    const displayed = page.getByText(withHistory || withTurn ? '开始「当前讲解」。' : '暂无聊天记录。');
    await displayed.waitFor();
    const writesBeforeReading = writes.length;
    const dialogue = page.getByRole('region', { name: '学习对话' });
    const directory = page.getByRole('complementary', { name: '活动目录' });
    const fullLayout = await dialogue.boundingBox();
    const multiline = ['先找原量。', '求增加量。', '加回原量。', '解释为什么。'].join('\n');
    await input.fill(multiline);
    assert.ok((await input.boundingBox()).height > inputBounds.height + 40, '多行输入自动增加高度');
    await input.press('Shift+Enter');
    assert.equal((await input.inputValue()).length, multiline.length + 1);
    await input.fill(Array(10).fill('用原量求增加量。').join('\n'));
    assert.ok(await input.evaluate((field) => field.scrollHeight > field.clientHeight));
    await input.fill(multiline);
    assert.equal(writes.length, writesBeforeReading);
    await page.screenshot({ path: path.join(evidence, 'composer-multiline.png') });

    await page.getByRole('button', { name: '收起目录', exact: true }).click();
    await directory.waitFor({ state: 'hidden' });
    assert.ok((await dialogue.boundingBox()).width > fullLayout.width + 200, '收起目录释放整列宽度');
    const showDirectory = page.getByRole('button', { name: '展开目录', exact: true });
    await showDirectory.waitFor();
    assert.ok(await showDirectory.evaluate((control) => control === document.activeElement));
    await page.screenshot({ path: path.join(evidence, 'activity-directory-hidden.png') });
    await showDirectory.click();
    await directory.waitFor();

    await input.fill('为什么需要加回原量？');
    for (const { title } of chapters) {
      await reader.getByRole('button', { name: title }).click();
      await page.getByRole('heading', { name: title + '（正文）' }).waitFor();
    }
    assert.equal(writes.length, writesBeforeReading);
    await page.screenshot({ path: path.join(evidence, 'study-layout.png'), fullPage: true });

    await page.getByRole('button', { name: '收起聊天' }).click();
    assert.equal(await displayed.isVisible(), false);
    assert.equal(await input.inputValue(), '为什么需要加回原量？');
    const paired = await dialogue.boundingBox();
    const hideReader = page.getByRole('button', { name: '收起教材', exact: true });
    assert.ok((await hideReader.boundingBox()).width <= 40);
    await closeReaderOnFocus(page, input);
    await reader.waitFor({ state: 'hidden' });
    assert.ok((await dialogue.boundingBox()).width > paired.width + 200);
    const showReader = page.getByRole('button', { name: '展开教材', exact: true });
    assert.ok((await showReader.boundingBox()).width <= 40);
    await showReader.click();
    await page.getByRole('heading', { name: '用两种方法解题（正文）' }).waitFor();
    assert.equal(writes.length, writesBeforeReading);

    if (withHistory) {
      await directory.getByRole('button', { name: '展开先前的讲解' }).click();
      await directory.getByRole('button', { name: child.name }).click();
      await page.locator('#study-message-' + child.first_message_ref + '.selected').waitFor();
      await page.getByRole('region', { name: '学习对话' }).getByText(active.name, { exact: true }).waitFor();
      assert.equal(writes.length, writesBeforeReading);
      await page.screenshot({ path: path.join(evidence, 'activity-history.png'), fullPage: true });
      await page.getByRole('button', { name: '回到当前' }).click();
      await displayed.waitFor();
      await page.getByRole('button', { name: '收起聊天' }).click();
    }

    await page.getByRole('button', { name: '收起教材' }).click();
    await page.reload();
    await page.getByRole('button', { name: '切换学习空间' }).waitFor();
    await page.getByRole('button', { name: '展开教材' }).waitFor();
    await page.getByRole('button', { name: '展开聊天' }).waitFor();
    await input.waitFor();
    if (withTurn) {
      await page.getByRole('button', { name: '展开聊天' }).click();
      const send = page.getByRole('button', { name: '发送', exact: true });
      const sendButton = await send.elementHandle();
      const sendBounds = await send.boundingBox();
      const draftsBeforeEnter = writes.length;
      await input.dispatchEvent('compositionstart');
      await input.press('Enter');
      await input.dispatchEvent('compositionend');
      assert.equal(writes.length, draftsBeforeEnter, '中文候选确认不发送');
      await input.fill('为什么需要加回原量？');
      await input.press('Enter');
      const stop = page.getByRole('button', { name: '停止本次回复' });
      await stop.waitFor();
      assert.ok(await sendButton.evaluate(
        (button) => button === document.querySelector('[aria-label="停止本次回复"]'),
      ));
      assert.equal((await stop.boundingBox()).x, sendBounds.x);
      await page.getByText('为什么需要加回原量？', { exact: true }).waitFor();
      await input.fill('下一条草稿');
      await stop.click();
      await page.getByText('已停止本次回复。', { exact: true }).waitFor();
      assert.equal(await input.inputValue(), '下一条草稿');
      assert.equal(writes.filter((route) => route.endsWith('/inputs')).length, 1);
      await page.screenshot({ path: path.join(evidence, 'student-input.png'), fullPage: true });
      console.log('Verified lost acceptance receipt, exact-once send, stopped reply and preserved draft.');
    }
    await checkHeader(page, evidence, space);
    assert.deepEqual(errors, []);
    console.log('Verified single-row header, long title, picker anchoring, account and textbook controls.');
    console.log('Verified default panes, chapter reading, draft preservation and layout after re-entry.');
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
