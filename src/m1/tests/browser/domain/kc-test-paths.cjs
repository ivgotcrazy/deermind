// 在真实管理端验证仅引用、只代入、确认及 Task 升版。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const domainName = process.env.M1_TEST_RICH_DOMAIN_NAME;
const observed = '解释每单位时间的路程如何累加，并指出速度须保持不变。';
const insufficient = '只把 3 和 4 代入得 12。';
const reason = '这一任务只要求计算结果，没有要求解释路程如何累加。';

function textBody(text) {
  return {
    schema_version: '1', role: 'definition', source_refs: [], data_tables: [],
    blocks: [{
      block_id: 'p1', type: 'paragraph', payload: { spans: [{ type: 'text', text }] },
      provenance: { transformation: 'generated', source_refs: [], note: '' },
    }],
  };
}

async function save(page, session, body) {
  const response = await page.request.post(origin + '/api/m1/domain-definitions', {
    data: { request_id: randomUUID(), change_note: 'E02-06 浏览器验收', ...body },
    headers: {
      Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token,
    },
  });
  assert.equal(response.status(), 200, await response.text());
  return (await response.json()).result.object_ref;
}

async function main() {
  assert.ok(domainName && evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 920 } });
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: '新建领域' }).waitFor();
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const root = await save(page, session, {
      action: 'create', object_kind: 'domain', definition: { name: domainName },
    });
    const domain_id = root.object_id;
    async function create(kind, definition) {
      return save(page, session, { domain_id, action: 'create', object_kind: kind, definition });
    }
    const kc = await create('kc', {
      name: '匀速路程公式为何成立',
      definition: textBody('匀速时，每单位时间经过相同路程。'),
      applicability: textBody('匀速且单位一致。'),
    });
    const method = await create('solution', {
      name: '按单位时间累加',
      rationale: textBody('每单位时间经过相同路程。'),
      applicability: textBody('速度恒定，时间与速度使用相容单位。'),
      key_process: textBody('以乘法表示相同路程的反复累加。'),
      kc_refs: [kc],
    });
    const explanation = {
      name: '解释 d=v×t',
      responsibility: textBody('解释速度、时间和路程之间的关系。'),
      expected_output: textBody(observed),
      completion_conditions: textBody('说明速度和时间的意义，指出匀速和单位条件。'),
      method_refs: [method],
    };
    const good = await create('task', explanation);
    await create('task', {
      name: '代入数值求路程',
      responsibility: textBody('计算 3×4。'),
      expected_output: textBody('给出正确数值。'),
      completion_conditions: textBody('算得 12 千米。'),
      method_refs: [method],
    });
    await page.reload();
    await page.getByRole('table', { name: '领域列表' }).getByRole('button', { name: domainName }).click();
    await page.getByRole('navigation', { name: '领域对象' }).getByRole('button', { name: '任务', exact: true }).click();

    const paths = page.getByRole('region', { name: '知识成分及检验路径' });
    const dialog = page.getByRole('dialog');
    async function fillCheck() {
      await paths.getByRole('button', { name: '核对检验路径' }).click();
      await dialog.getByLabel('应观察到的表现').fill(observed);
      await dialog.getByLabel('不足示例（每行一条）').fill(insufficient);
    }

    await page.getByRole('button', { name: /代入数值求路程 v1/ }).click();
    await paths.getByText('仅引用，待确认').waitFor();
    await fillCheck();
    await dialog.getByLabel('核对结论').selectOption('insufficient');
    await dialog.getByLabel('不足原因').fill(reason);
    await dialog.getByRole('button', { name: '记录不足' }).click();
    await paths.getByRole('status').filter({ hasText: '已记录检验依据不足。' }).waitFor();
    await paths.getByText(reason, { exact: true }).waitFor();
    assert.equal(await paths.getByText('查看已确认的检验依据').count(), 0);
    await page.screenshot({ path: path.join(evidence, 'insufficient-path.png'), fullPage: true });

    await page.getByRole('button', { name: /解释 d=v×t v1/ }).click();
    await page.getByRole('region', { name: /解释 d=v×t v1/ }).getByRole('button', { name: '核对检验路径' }).waitFor();
    await fillCheck();
    let original;
    await page.route('**/kc-test-paths', async (route) => {
      const response = await route.fetch();
      assert.equal(response.status(), 200, await response.text());
      original = (await response.json()).result.confirmation_ref;
      await route.abort();
    }, { times: 1 });
    await dialog.getByRole('button', { name: '保存确认' }).click();
    await paths.getByRole('status').filter({ hasText: '检验路径已确认。' }).waitFor();
    assert.ok(original);
    await paths.getByText('查看已确认的检验依据').click();
    await paths.getByText(observed, { exact: true }).waitFor();
    await page.screenshot({ path: path.join(evidence, 'confirmed-path.png'), fullPage: true });

    const revision = await save(page, session, {
      action: 'update', object_kind: 'task', object_ref: good, expected_version: 1,
      definition: { ...explanation, completion_conditions: textBody('补充速度与时间单位应相容。') },
    });
    assert.equal(revision.version, 2);
    await page.getByRole('button', { name: /解释 d=v×t v1/ }).click();
    const focus = page.getByRole('region', { name: /解释 d=v×t v2/ });
    await focus.getByText('仅引用，待确认').waitFor();
    assert.equal(await paths.getByText('查看已确认的检验依据').count(), 0);
    await focus.getByLabel('版本', { exact: true }).fill('1');
    await focus.getByRole('button', { name: '查看版本' }).click();
    await paths.getByText('查看已确认的检验依据').click();
    await paths.getByText(observed, { exact: true }).waitFor();
    await writeFile(path.join(evidence, 'results.json'), JSON.stringify({
      domainName, domainId: domain_id, original, version1: good, version2: revision,
    }, null, 2));
    console.log('E02-06 browser: only linked, insufficient basis, recovered confirmation and fixed history verified');
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
