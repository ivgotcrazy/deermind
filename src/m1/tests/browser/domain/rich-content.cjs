// 同一 K3s 管理端验证正式领域存取，并用已回读夹具覆盖共享渲染器。
const assert = require('node:assert/strict');
const { createHash, randomUUID } = require('node:crypto');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const domainsPath = '/api/m1/domains';
const evidenceDir = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const domainName = process.env.M1_TEST_RICH_DOMAIN_NAME;
const login = process.env.M1_TEST_DOMAIN_LOGIN;
const password = process.env.M1_TEST_DOMAIN_PASSWORD;
const provenance = { source_refs: [], transformation: 'generated', note: '' };
const sampleTitle = '验收说明 <b>保留原文</b>';

function richText(blocks) {
  return { schema_version: '1', role: 'definition', blocks, data_tables: [], source_refs: [] };
}

function paragraph(blockId, spans) {
  return { block_id: blockId, type: 'paragraph', provenance, payload: { spans } };
}

function createBody() {
  const fraction = {
    op: 'fraction',
    args: [
      { op: 'number', value: '3' },
      { op: 'number', value: '4' },
    ],
  };
  const coverage = richText([paragraph('range', [{ type: 'text', text: '合成覆盖范围' }])]);
  const description = richText([
    paragraph('explanation', [
      { type: 'text', text: sampleTitle },
      { type: 'math', expression: fraction },
    ]),
  ]);
  return {
    // 同一验收编号的复测沿用原写入，保留一个供用户核对的合成领域。
    request_id: createHash('sha256').update(`rich-content:${domainName}`).digest('hex'),
    object_kind: 'domain',
    action: 'create',
    // 普通合成内容与长变更说明提交为一个正式版本，触发实际 PVC 读写。
    definition: { name: domainName, coverage, description },
    change_note: '附件验证'.repeat(3000),
  };
}

async function snapshot(page, name) {
  if (evidenceDir) {
    await page.screenshot({ path: path.join(evidenceDir, `${name}.png`), fullPage: true });
  }
}

async function openDomain(page, name) {
  const list = page.getByRole('table', { name: '领域列表' });
  await list.getByRole('button', { name }).click();
  const detail = page.locator('.domain-detail');
  await detail.getByRole('heading', { name, exact: true }).waitFor();
  return detail;
}

async function verifyDefinition(page, headers, session) {
  const list = await page.request.get(origin + domainsPath, { headers });
  assert.equal(list.status(), 200);
  const existing = (await list.json()).items.find((item) => item.name.startsWith('E02-01 验收 '));
  assert.ok(existing, 'Keep the E02-01 acceptance root for compatibility verification.');
  const oldRef = existing.object_ref.object_id;
  const old = await page.request.get(origin + `${domainsPath}/${oldRef}/objects/${oldRef}`, {
    headers,
    params: { version: 1 },
  });
  assert.equal(old.status(), 200);
  assert.equal((await old.json()).object.content.description, null);

  const body = createBody();
  const invalid = structuredClone(body);
  invalid.request_id = randomUUID();
  invalid.definition.description.blocks[0].payload.spans[1].expression.args.pop();
  const rejected = await page.request.post(origin + '/api/m1/domain-definitions', {
    headers,
    data: invalid,
  });
  assert.equal(rejected.status(), 400);
  const issues = (await rejected.json()).error.issues;
  assert.ok(issues.some((issue) => issue.path.startsWith('/definition/description/blocks')));
  const empty = await page.request.get(origin + '/api/m1/requests/receipt', {
    headers,
    params: {
      action: 'domain.save_definition',
      resource_kind: 'account',
      resource_id: session.account.account_id,
      request_id: invalid.request_id,
    },
  });
  assert.equal(empty.status(), 200);
  assert.equal((await empty.json()).receipt_state, 'not_found');

  const saved = await page.request.post(origin + '/api/m1/domain-definitions', {
    headers,
    data: body,
  });
  assert.equal(saved.status(), 200, await saved.text());
  const { result } = await saved.json();
  assert.equal(result.object_ref.version, 1);
  const id = result.object_ref.object_id;
  const detailUrl = origin + `${domainsPath}/${id}/objects/${id}`;
  const fixed = await page.request.get(detailUrl, { headers, params: { version: 1 } });
  assert.equal(fixed.status(), 200);
  const { object } = await fixed.json();
  assert.equal(object.content.coverage.blocks[0].payload.spans[0].text, '合成覆盖范围');
  assert.equal(object.content.description.blocks[0].payload.spans[0].text, sampleTitle);

  await page.reload();
  const frame = await openDomain(page, domainName);
  const rendered = frame.locator('[data-rich-field="description"]');
  await rendered.getByText(sampleTitle).waitFor();
  assert.equal(await rendered.locator('b').count(), 0);
  assert.equal(await rendered.locator('math mfrac').count(), 1);
  assert.equal(
    await rendered.locator('mfrac').evaluate((element) => element.namespaceURI),
    'http://www.w3.org/1998/Math/MathML',
  );
  await frame.locator('[data-rich-field="coverage"]').getByText('合成覆盖范围').waitFor();
  await snapshot(page, 'deployed-definition');
  await page.getByRole('button', { name: '返回领域列表' }).click();
  return { detailUrl, sourceEventId: object.source_event_id, validationIssues: issues };
}

async function renderFixture(page, detailUrl, fixture) {
  // 只在本测试页的同一条详情请求替换为从集群回读的角色正文。
  const inject = async (route) => {
    const response = await route.fetch();
    assert.equal(response.status(), 200);
    const detail = await response.json();
    detail.object.content.coverage = null;
    detail.object.content.description = fixture.content;
    await route.fulfill({ response, json: detail });
  };
  await page.route(detailUrl, inject, { times: 1 });
  try {
    await openDomain(page, domainName);
    const rendered = page.locator(`.rich-content[data-role="${fixture.content.role}"]`);
    await rendered.waitFor();
    assert.equal(await rendered.locator('[data-block-id]').count(), fixture.content.blocks.length);
    switch (fixture.content.role) {
      case 'reference':
        assert.ok(await rendered.locator('math [data-cancellation]').count());
        break;
      case 'derived_view':
        assert.equal(await rendered.locator('table').count(), 2);
        await rendered.getByRole('cell', { name: '1.30', exact: true }).waitFor();
        break;
    }
    if (fixture.id === 'C03-question') {
      const formula = await rendered.locator('math').allTextContents();
      assert.ok(formula[0].includes('÷') && formula[1].includes('×'));
      assert.match(formula.at(-1), /7\s*32/);
    }
    if (fixture.id === 'C05-question') {
      for (const kind of ['bar', 'line', 'pie']) {
        await rendered.locator(`figure[data-chart="${kind}"] svg`).waitFor();
      }
      const bars = rendered.locator('figure[data-chart="bar"]');
      assert.equal(await bars.getAttribute('data-relationship'), 'overlapping_populations');
      await bars.locator('figcaption').getByText('（亿人）', { exact: true }).waitFor();
    }
    if (fixture.id === 'C05-missing-value') {
      const bars = rendered.locator('figure[data-chart="bar"]');
      await bars.getByText('当前无法按原数据绘制图表，请查阅数据表。').waitFor();
      await bars.getByRole('cell', { name: '原文未提供', exact: true }).waitFor();
      assert.equal(await bars.locator('svg').count(), 0);
    }
    if (fixture.id === 'C06-question') {
      await rendered.locator('figure[data-diagram] svg').waitFor();
      assert.equal(await rendered.locator('[data-shape="point"]').count(), 6);
      await rendered.getByText(/附页1图1不在既定四例材料内/).waitFor();
    }
    assert.match(fixture.id, /^C\d{2}-[a-z-]+$/);
    await snapshot(page, fixture.id);
    if (fixture.id === 'C05-question') {
      const viewport = page.viewportSize();
      assert.ok(viewport);
      await page.setViewportSize({ width: 390, height: 844 });
      assert.equal(
        await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
        false,
      );
      await snapshot(page, 'C05-mobile');
      await page.setViewportSize(viewport);
    }
    await page.getByRole('button', { name: '返回领域列表' }).click();
  } finally {
    await page.unroute(detailUrl, inject);
  }
}

async function run() {
  assert.equal(new URL(origin).hostname, '127.0.0.1');
  assert.match(domainName ?? '', /^E02-02 验收 [a-z0-9-]+$/);
  assert.ok(login && password && process.env.M1_TEST_CONTENT_OUTPUT);
  const fixtures = JSON.parse(await readFile(process.env.M1_TEST_CONTENT_OUTPUT, 'utf8'));
  assert.deepEqual(Object.keys(fixtures), ['C02', 'C03', 'C05', 'C06']);
  if (evidenceDir) await mkdir(evidenceDir, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage();
    let pageErrors = 0;
    page.on('pageerror', () => pageErrors++);
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(login);
    await page.getByLabel('密码').fill(password);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('table', { name: '领域列表' }).waitFor();
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    assert.equal(session.account.role, 'admin');
    const headers = {
      Origin: origin,
      'X-Expected-Session': session.session_id,
      'X-CSRF-Token': session.csrf_token,
    };
    const accepted = await verifyDefinition(page, headers, session);
    for (const { documents } of Object.values(fixtures)) {
      for (const fixture of documents) await renderFixture(page, accepted.detailUrl, fixture);
    }
    const missing = structuredClone(fixtures.C05.documents[0]);
    missing.id = 'C05-missing-value';
    missing.content.data_tables[0].rows[0].cells.age60 = { state: 'source_missing' };
    await renderFixture(page, accepted.detailUrl, missing);
    await page.setViewportSize({ width: 390, height: 844 });
    await openDomain(page, domainName);
    assert.equal(await page.locator('.rich-content[data-role="definition"]').count(), 2);
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
      false,
    );
    assert.equal(pageErrors, 0);
    const output = {
      browser: `Chromium ${browser.version()}`,
      origin,
      deployed_domain: {
        name: domainName,
        detail_url: accepted.detailUrl,
        source_event_id: accepted.sourceEventId,
        rejected_issue_paths: accepted.validationIssues.map(({ path }) => path),
        existing_e0201_v1_readable: true,
      },
      fixture_browser: {
        input: 'restored test files from the K3s acceptance Pod',
        cases: Object.keys(fixtures),
        source_missing_shown_without_plotting: true,
        missing_c06_insert_shown: true,
        roles_rendered: Object.values(fixtures).flatMap(({ documents }) =>
          documents.map(({ id, content }) => ({ id, role: content.role })),
        ),
      },
    };
    if (evidenceDir) {
      await writeFile(path.join(evidenceDir, 'browser.json'), JSON.stringify(output, null, 2) + '\n');
    }
    console.log(JSON.stringify(output));
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
