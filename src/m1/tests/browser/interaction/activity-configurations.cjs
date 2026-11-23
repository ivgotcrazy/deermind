// Exercise the activity configuration UI and immutable revisions against the K3s release.
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

async function run() {
  const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
  const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
  assert.ok(origin && evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  const page = await browser.newPage({ viewport: { width: 1340, height: 1060 } });
  try {
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: '交互活动', exact: true }).click();
    const workspace = page.getByRole('region', { name: '交互活动' });
    const root = origin + '/api/m1';
    const session = await (await page.request.get(root + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    async function read(type, ref = '', status = 200) {
      const response = await page.request.get(root + '/interaction/activity-configs/' + type + ref, { headers });
      assert.equal(response.status(), status, await response.text());
      return response.json();
    }
    async function put(type, data, status = 200) {
      const response = await page.request.put(root + '/interaction/activity-configs/' + type, { headers, data });
      assert.equal(response.status(), status, await response.text());
      return response.json();
    }
    const activityTypes = {
      explanation: '讲解',
      question_answer: '答疑',
      detection: '检测',
      free_chat: '自由交谈',
    };
    const snapshots = {};
    for (const [type, label] of Object.entries(activityTypes)) {
      await workspace.getByRole('navigation', { name: '活动类型' }).getByRole('button', { name: label, exact: true }).click();
      const existing = await page.request.get(root + '/interaction/activity-configs/' + type, { headers });
      const first = existing.status() === 404;
      assert.ok(first || existing.ok(), await existing.text());
      await workspace.getByRole('button', { name: '保存蓝图' }).click();
      await workspace.getByRole('status').filter({ hasText: '已保存修订' }).waitFor();
      const saved = await read(type);
      assert.deepEqual(saved.definition.blueprint.nodes.map((node) => node.node_id).filter((id) => ['start', 'end'].includes(id)), ['start', 'end']);
      if (first) {
        assert.equal(saved.definition.binding_ref.revision, 1);
        assert.deepEqual(saved.definition.binding, { activity_type: type, activity: { rule_ids: [], strategy_ids: [] }, nodes: {} });
        assert.equal(saved.gaps[0].code, 'missing_activity_rules');
      }
      snapshots[type] = saved.config_ref;
    }
    const type = 'explanation';
    await workspace.getByRole('navigation', { name: '活动类型' }).getByRole('button', { name: '讲解', exact: true }).click();
    const original = await read(type);
    const version = original.config_ref.revision;
    const invalid = await put(type, {
      request_id: randomUUID(), config_kind: 'blueprint', config_ref: original.definition.blueprint_ref,
      expected_revision: version,
      definition: { ...original.definition.blueprint, nodes: original.definition.blueprint.nodes.filter((node) => node.node_id !== 'end') },
    }, 400);
    assert.equal(invalid.error.code, 'invalid_blueprint');
    assert.deepEqual((await read(type)).config_ref, original.config_ref);
    const ruleName = '引用学生原话 ' + randomUUID().slice(0, 6);
    await workspace.getByRole('button', { name: '新建规则' }).click();
    await workspace.getByLabel('规则名称').fill(ruleName);
    await workspace.getByLabel('规则内容').fill('澄清时引用学生的原话。');
    await workspace.getByRole('button', { name: '保存规则' }).click();
    await workspace.getByRole('status').filter({ hasText: `已保存修订 ${version + 1}` }).waitFor();
    await workspace.getByLabel('配置位置').selectOption('');
    await workspace.getByRole('checkbox', { name: ruleName }).check();
    await workspace.getByRole('button', { name: '保存作用范围' }).click();
    await workspace.getByRole('status').filter({ hasText: `已保存修订 ${version + 2}` }).waitFor();
    const bound = await read(type);
    assert.deepEqual(bound.gaps, []);
    assert.equal(bound.definition.binding.activity.rule_ids.length, original.definition.binding.activity.rule_ids.length + 1);
    await workspace.getByLabel('配置位置').selectOption('step-1');
    assert.ok(!(await workspace.getByRole('checkbox', { name: ruleName }).isChecked()));
    const old = await read(type, '?config_ref=' + original.config_ref.id);
    assert.deepEqual(old, original);
    await put(type, {
      request_id: randomUUID(), config_kind: 'binding', config_ref: original.definition.binding_ref,
      expected_revision: version, definition: original.definition.binding,
    }, 409);
    await page.screenshot({ path: path.join(evidence, 'activity-configuration.png'), fullPage: true });
    await writeFile(path.join(evidence, 'activity-revisions.json'), JSON.stringify({ snapshots, bound: bound.config_ref }, null, 2));
    console.log('Verified four activity blueprints, initial empty binding, binding scope, historical revision and rejection of invalid/stale updates.');
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
