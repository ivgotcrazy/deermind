// 在已部署的学生端验证布局。课程和章节响应使用固定夹具，登录走实际服务。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

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
    await page.getByLabel('密码').fill(password);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: /退出登录/ }).waitFor();

    const chapters = ['原量与新量', '用两种方法解题'].map((title) => ({
      title, chapter_id: randomUUID(), revision: 1, page_refs: [], content_refs: [], associations: [],
    }));
    const space = {
      space_id: randomUUID(), student_id: randomUUID(), student_name: '合成学生',
      textbook_id: randomUUID(), textbook_title: '分数学习样例', target_id: randomUUID(),
      target_title: '增加四分之一', created_at: new Date().toISOString(),
    };
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
      if (request.method() === 'POST') writes.push(new URL(request.url()).pathname);
    });
    await page.route('**/api/m1/course-options', (route) =>
      route.fulfill({ json: { items: [], next_cursor: null } }));
    await page.route('**/api/m1/learning-spaces', (route) =>
      route.fulfill({ json: { items: [space], next_cursor: null } }));
    await page.route('**/api/m1/learning-spaces/open', (route) =>
      route.fulfill({ json: {
        request_ref: randomUUID(),
        result: { space, created: false, adoption: { snapshot: { chapters } } },
      } }));
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
      page.getByRole('heading', { name: '选择教材和目标' }).waitFor(),
    ]);
    if (await consent.isVisible()) await consent.click();
    const enter = page.getByRole('button', { name: '分数学习样例 · 增加四分之一' });
    await enter.click();
    const reader = page.getByRole('navigation', { name: '教材章节' });
    const input = page.getByLabel('输入消息');
    await reader.waitFor();
    await input.waitFor();
    const displayed = page.getByText(withHistory || withTurn ? '开始「当前讲解」。' : '暂无聊天记录。');
    await displayed.waitFor();
    const writesBeforeReading = writes.length;
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
    await page.getByRole('button', { name: '收起教材' }).click();
    await reader.waitFor({ state: 'hidden' });
    await page.getByRole('button', { name: '展开教材' }).click();
    await page.getByRole('heading', { name: '用两种方法解题（正文）' }).waitFor();
    assert.equal(writes.length, writesBeforeReading);

    if (withHistory) {
      const directory = page.getByRole('complementary', { name: '活动目录' });
      await directory.getByRole('button', { name: '展开先前的讲解' }).click();
      await directory.getByRole('button', { name: child.name }).click();
      await page.locator('#study-message-' + child.first_message_ref + '.selected').waitFor();
      await page.getByRole('region', { name: '学习对话' }).getByText(active.name, { exact: true }).waitFor();
      assert.equal(writes.length, writesBeforeReading);
      await page.screenshot({ path: path.join(evidence, 'activity-history.png'), fullPage: true });
      await page.getByRole('button', { name: '收起聊天' }).click();
    }

    await page.getByRole('button', { name: '收起教材' }).click();
    await page.reload();
    await enter.click();
    await page.getByRole('button', { name: '展开教材' }).waitFor();
    await page.getByRole('button', { name: '展开聊天' }).waitFor();
    await input.waitFor();
    if (withTurn) {
      await page.getByRole('button', { name: '展开聊天' }).click();
      await page.getByRole('button', { name: '发送', exact: true }).click();
      const stop = page.getByRole('button', { name: '停止本次回复' });
      await stop.waitFor();
      await page.getByText('为什么需要加回原量？', { exact: true }).waitFor();
      await input.fill('下一条草稿');
      await stop.click();
      await page.getByText('已停止本次回复。', { exact: true }).waitFor();
      assert.equal(await input.inputValue(), '下一条草稿');
      assert.equal(writes.filter((route) => route.endsWith('/inputs')).length, 1);
      await page.screenshot({ path: path.join(evidence, 'student-input.png'), fullPage: true });
      console.log('Verified lost acceptance receipt, exact-once send, stopped reply and preserved draft.');
    }
    assert.deepEqual(errors, []);
    console.log('Verified default panes, chapter reading, draft preservation and layout after re-entry.');
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
