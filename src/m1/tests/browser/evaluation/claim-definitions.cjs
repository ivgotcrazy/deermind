// 验证同一 Task 的两种方法可独立关联判据和方面规则，旧定义可回读。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

async function run() {
  const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
  const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
  assert.ok(evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  const page = await browser.newPage({ viewport: { width: 1340, height: 1060 } });
  try {
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const menu = page.getByRole('navigation', { name: '管理功能' });
    await menu.waitFor();
    const root = origin + '/api/m1';
    const session = await (await page.request.get(root + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    async function read(url) {
      const response = await page.request.get(root + url, { headers });
      assert.equal(response.status(), 200, await response.text());
      return response.json();
    }
    async function post(url, body, status = 200) {
      const response = await page.request.post(root + url, { headers, data: body });
      assert.equal(response.status(), status, await response.text());
      return response.json();
    }
    async function define(object_kind, definition, domain_id) {
      const result = await post('/domain-definitions', {
        request_id: randomUUID(), object_kind, definition, domain_id, action: 'create', change_note: 'E03-01 集群验证',
      });
      return result.result.object_ref;
    }

    const domainName = 'E03 四分之一 ' + randomUUID().slice(0, 7);
    const { object_id: domain } = await define('domain', { name: domainName });
    const first = await define('solution', { name: '先求增加量' }, domain);
    const second = await define('solution', { name: '先求增加后的倍数' }, domain);
    const unrelated = await define('solution', { name: '已知面积求边长' }, domain);
    const task = await define('task', { name: '一个量增加四分之一', method_refs: [first, second] }, domain);
    await define('task', { name: '一个与分数无关的任务', method_refs: [unrelated] }, domain);
    const route = '/evaluation/claim-commands';
    await menu.getByRole('button', { name: '评估管理' }).click();
    const workspace = page.getByRole('region', { name: '评估管理' });
    await workspace.getByLabel('领域').selectOption(domain);
    const createForm = workspace.getByRole('button', { name: '创建 Claim', exact: true }).locator('..');
    await createForm.getByLabel('任务').selectOption(task.object_id);
    await createForm.getByLabel('名称').fill('四分之一的两种方法');
    await createForm.getByLabel('说明').fill('考察学生使用已知原量和增加比例求新量。');
    await createForm.getByRole('button', { name: '创建 Claim' }).click();
    const methodNav = workspace.getByRole('navigation', { name: '任务方法' });
    await methodNav.getByRole('button', { name: '先求增加量', exact: true }).waitFor();
    await methodNav.getByRole('button', { name: '先求增加后的倍数', exact: true }).waitFor();
    const { items } = await read('/evaluation/claims?domain_id=' + domain);
    assert.equal(items.length, 1);
    const { claim_id: claimId } = items[0].claim_ref;
    const fixed = (await read(`/evaluation/claims/${claimId}?revision=1`)).claim;
    assert.deepEqual(fixed.definition.methods.map((entry) => entry.method_ref), [first, second]);
    assert.equal(fixed.definition.aspects.length, 4);
    assert.equal(fixed.gaps.length, 10);

    await workspace.getByRole('button', { name: '添加判据' }).click();
    const dialog = page.getByRole('dialog', { name: '添加判据' });
    await dialog.getByLabel('名称').fill('求出原量的四分之一');
    await dialog.getByLabel('判断依据').fill('核对增加量的计算过程。');
    await dialog.getByLabel('符合时', { exact: true }).fill('把原量乘四分之一。');
    await dialog.getByLabel('不符合时', { exact: true }).fill('把比例作用在新量。');
    await dialog.getByLabel('证据不足时').fill('只给出一个无过程的数字。');
    await dialog.getByRole('button', { name: '保存判据' }).click();
    await dialog.waitFor({ state: 'hidden' });
    await workspace.getByRole('checkbox', { name: '求出原量的四分之一' }).check();
    await workspace.getByRole('button', { name: '保存方法判据' }).click();
    await workspace.getByRole('status').filter({ hasText: '第 3 版' }).waitFor();
    const prepare = (await read(`/evaluation/claims/${claimId}`)).claim;
    const criterion = prepare.definition.criteria[0].criterion_id;
    assert.deepEqual(prepare.definition.methods.map((entry) => entry.criterion_ids), [[criterion], []]);

    function update(action, fields, revision = 3) {
      return { request_id: randomUUID(), action, domain_id: domain, task_ref: task,
        claim_id: claimId, expected_revision: revision, ...fields };
    }
    const foreign = await post(route, update('set_method_criteria', {
      method_ref: unrelated, criterion_ids: [criterion],
    }), 409);
    assert.equal(foreign.error.code, 'invalid_reference');
    const foreignCriterion = await post(route, update('set_method_criteria', {
      method_ref: first, criterion_ids: [randomUUID()],
    }), 409);
    assert.equal(foreignCriterion.error.code, 'invalid_reference');
    const linked = await post(route, update('remove_criterion', { criterion_id: criterion }), 409);
    assert.equal(linked.error.code, 'criterion_in_use');
    const noChange = update('set_method_criteria', { method_ref: first, criterion_ids: [criterion] });
    const unchanged = await post(route, noChange);
    assert.equal(unchanged.result.changed, false);
    assert.deepEqual(await post(route, noChange), unchanged);

    const aspect = update('save_aspect_rule', { method_ref: second, rule: {
      aspect_code: 'independent', judgement_basis: '独立完成列式和计算。', evidence_requirements: ['有求新量的作答'],
      condition_schema: { type: 'object', properties: { help: { type: 'string', enum: ['none'] } } }, default_values: { help: 'none' },
    } });
    const saved = await post(route, aspect);
    assert.equal(saved.result.claim_ref.revision, 4);
    const conflict = await post(route, update('set_method_criteria', { method_ref: second, criterion_ids: [criterion] }), 409);
    assert.equal(conflict.error.code, 'revision_conflict');
    assert.deepEqual(await post(route, aspect), saved);
    const receipt = await read('/requests/receipt?' + new URLSearchParams({
      action: 'evaluation.manage_claim', resource_kind: 'domain', resource_id: domain, request_id: aspect.request_id,
    }));
    assert.equal(receipt.receipt_ref, saved.request_ref);
    assert.deepEqual(receipt.result, saved.result);
    assert.deepEqual((await read(`/evaluation/claims/${claimId}?revision=1`)).claim, fixed);
    const current = (await read(`/evaluation/claims/${claimId}`)).claim;
    assert.equal(current.definition.methods[0].aspect_rules.length, 0);
    assert.equal(current.definition.methods[1].aspect_rules[0].aspect_code, 'independent');
    await menu.getByRole('button', { name: '领域管理' }).click();
    await menu.getByRole('button', { name: '评估管理' }).click();
    await workspace.getByLabel('领域').selectOption(domain);
    await workspace.getByRole('button', { name: '四分之一的两种方法 · v4' }).click();
    await methodNav.getByRole('button', { name: '先求增加后的倍数', exact: true }).click();
    await page.screenshot({ path: path.join(evidence, 'claim-two-methods.png'), fullPage: true });
    await workspace.getByRole('button', { name: '编辑 Claim 基本信息' }).click();
    const basics = page.getByRole('dialog', { name: '编辑 Claim 基本信息' });
    await basics.getByRole('checkbox', { name: '保持', exact: true }).uncheck();
    await basics.getByRole('button', { name: '保存基本信息' }).click();
    await basics.getByRole('alert').filter({ hasText: '调整理由' }).waitFor();
    await basics.getByLabel('调整理由').fill('本阶段只核对近期表现。');
    await basics.getByRole('button', { name: '保存基本信息' }).click();
    await basics.waitFor({ state: 'hidden' });
    const narrowed = (await read(`/evaluation/claims/${claimId}`)).claim;
    assert.equal(narrowed.claim_ref.revision, 5);
    assert.deepEqual(narrowed.definition.aspects.map((entry) => entry.code), ['independent', 'understanding', 'transfer']);
    assert.equal((await read(`/evaluation/claims/${claimId}?revision=4`)).claim.definition.aspects.length, 4);
    const revisedTask = (await post('/domain-definitions', {
      request_id: randomUUID(), object_kind: 'task', action: 'update',
      object_ref: task, expected_version: 1, change_note: '保留两种直接方法',
      definition: { name: '一个量增加四分之一（第二版）', method_refs: [first, second] },
    })).result.object_ref;
    const newClaim = (await post(route, {
      request_id: randomUUID(), action: 'create_claim', domain_id: domain, task_ref: revisedTask,
      title: '第二版任务的 Claim', description: '采用新版任务另行配置。', aspects: fixed.definition.aspects,
    })).result.claim_ref;
    const fresh = (await read(`/evaluation/claims/${newClaim.claim_id}`)).claim;
    assert.notEqual(newClaim.claim_id, claimId);
    assert.equal(fresh.definition.task_ref.version, 2);
    assert.deepEqual(fresh.definition.criteria, []);
    assert.equal((await read(`/evaluation/claims/${claimId}`)).claim.definition.task_ref.version, 1);
    await writeFile(path.join(evidence, 'claim-revisions.json'), JSON.stringify({ fixed, current, receipt, narrowed, fresh }, null, 2));
    console.log('E03-01 Claim versions, independent method rules, stale and foreign references verified.');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
