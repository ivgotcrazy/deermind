// 在既有 K3s 管理端复验两个 Task、参数和版本冲突。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const domainName = process.env.M1_TEST_RICH_DOMAIN_NAME;
const writePath = '/api/m1/domain-definitions';
const explanation = '解释匀速路程关系';
const calculation = '根据速度和时间求路程';

async function save(page, session, body) {
  const response = await page.request.post(origin + writePath, {
    data: body,
    headers: {
      Origin: origin,
      'X-Expected-Session': session.session_id,
      'X-CSRF-Token': session.csrf_token,
    },
  });
  assert.equal(response.status(), 200, await response.text());
  return response.json();
}

async function read(page, session, route, params) {
  const response = await page.request.get(origin + route, {
    params,
    headers: { 'X-Expected-Session': session.session_id },
  });
  assert.equal(response.status(), 200, await response.text());
  return response.json();
}

async function fillTask(dialog, name, fields) {
  await dialog.getByLabel('名称', { exact: true }).fill(name);
  for (const [label, value] of Object.entries(fields)) {
    await dialog.getByLabel(label, { exact: true }).fill(value);
  }
  await dialog.getByLabel('变更原因').fill('E02-04 验收');
}

async function main() {
  assert.ok(domainName && evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 920 } });
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error.name));
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: '新建领域' }).waitFor();
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const root = await save(page, session, {
      request_id: randomUUID(), object_kind: 'domain', action: 'create',
      definition: { name: domainName }, change_note: 'E02-04 合成领域验收',
    });
    const domainId = root.result.object_ref.object_id;
    await page.reload();
    await page.getByRole('list', { name: '领域列表' }).getByRole('button', { name: domainName }).click();
    await page.getByRole('navigation', { name: '领域对象' }).getByRole('button', { name: '任务' }).click();
    const create = page.getByRole('button', { name: '新建任务', exact: true });
    const dialog = page.getByRole('dialog');
    await create.click();
    await fillTask(dialog, explanation, {
      认知责任: '解释每单位时间的路程怎样累积。',
      预期表现: '用自己的话说明 d=v×t 为什么成立。',
      完成条件: '说清每个量的含义，并说明需要保持匀速。',
      适用条件: '速度保持不变，时间与速度的单位相容。',
      适用边界: '排除变速运动。',
    });
    await dialog.getByText('参数（可选）', { exact: true }).click();
    await dialog.getByRole('button', { name: '添加参数' }).click();
    await dialog.getByLabel('参数名称').fill('t');
    await dialog.getByLabel('含义', { exact: true }).fill('行进时间');
    await dialog.getByLabel('类型', { exact: true }).fill('数值');
    await dialog.getByLabel('约束', { exact: true }).fill('t > 0，单位与速度相容');
    await dialog.getByRole('button', { name: '保存', exact: true }).click();
    const first = page.getByRole('region', { name: /解释匀速路程关系/ });
    await first.getByText('尚未关联方法。').waitFor();
    await first.getByText('行进时间。t > 0，单位与速度相容').waitFor();
    const catalog = `/api/m1/domains/${domainId}/objects`;
    const [initial] = (await read(page, session, catalog, { kinds: 'task' })).items;
    const originalPath = `${catalog}/${initial.object_ref.object_id}`;
    const before = (await read(page, session, originalPath)).object;
    assert.equal(before.object_ref.version, 1);
    assert.deepEqual(before.gaps.map((gap) => gap.path), ['/method_refs']);

    await create.click();
    await fillTask(dialog, calculation, { 认知责任: '将题目给出的速度和时间代入，计算路程。' });
    await dialog.getByRole('button', { name: '保存', exact: true }).click();
    const second = page.getByRole('region', { name: /根据速度和时间求路程/ });
    await second.getByText('请补充完成条件。').waitFor();
    const list = await read(page, session, catalog, { kinds: 'task' });
    assert.deepEqual(list.items.map((item) => item.name).sort(), [explanation, calculation].sort());

    await page.getByRole('button', { name: /解释匀速路程关系 v1/ }).click();
    await first.getByRole('button', { name: '编辑' }).click();
    const conditions = dialog.getByLabel('适用条件', { exact: true });
    const draft = '这个编辑稿应保留，不能覆盖刚保存的新版本。';
    await conditions.fill(draft);
    await dialog.getByLabel('变更原因').fill('并发修订验证');
    const committed = await save(page, session, {
      request_id: randomUUID(), object_kind: 'task', action: 'update',
      object_ref: before.object_ref, expected_version: 1, change_note: '另一操作先保存边界',
      definition: { ...before.content, boundaries: null },
    });
    await dialog.getByRole('button', { name: '保存', exact: true }).click();
    await dialog.getByRole('alert').getByText('领域对象已变更，请核对最新版本。').waitFor();
    assert.equal(await conditions.inputValue(), draft);
    await dialog.getByRole('button', { name: '取消' }).click();
    await page.getByRole('button', { name: /解释匀速路程关系 v1/ }).click();
    await first.getByRole('heading', { name: /v2/ }).waitFor();
    await first.getByLabel('版本', { exact: true }).fill('1');
    await first.getByRole('button', { name: '查看版本' }).click();
    await first.getByText('排除变速运动。').waitFor();
    const history = (await read(page, session, originalPath, { version: 1 })).object;
    assert.deepEqual(history, before);
    assert.equal(pageErrors.length, 0);
    await page.screenshot({ path: path.join(evidence, 'task-history.png'), fullPage: true });
    await writeFile(path.join(evidence, 'results.json'), JSON.stringify({
      domainName, domainId, taskVersion1: before.object_ref, taskVersion2: committed.result.object_ref,
      draftGaps: (await read(page, session, `${catalog}/${list.items.find((item) => item.name === calculation).object_ref.object_id}`)).object.gaps,
    }, null, 2));
    console.log('E02-04 browser: distinct tasks, draft gaps, parameters, edit conflict and v1 verified');
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
