// 在已部署的 K3s 上验证知识成分的增删改、旧版读取和原请求恢复。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const domainName = process.env.M1_TEST_RICH_DOMAIN_NAME;
const writePath = '/api/m1/domain-definitions';
const definition = {
  schema_version: '1',
  role: 'definition',
  source_refs: [],
  data_tables: [],
  blocks: [
    {
      type: 'paragraph',
      block_id: 'statement',
      provenance: { transformation: 'generated', note: '', source_refs: [] },
      payload: {
        spans: [
          { type: 'text', text: '整体平均分成四份，其中一份是' },
          {
            type: 'math',
            expression: {
              op: 'fraction',
              args: [{ op: 'number', value: '1' }, { op: 'number', value: '4' }],
            },
          },
        ],
      },
    },
  ],
};

async function save(page, session, body) {
  const response = await page.request.post(origin + writePath, {
    data: body,
    headers: { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token },
  });
  assert.equal(response.status(), 200, await response.text());
  return response.json();
}

async function read(page, session, pathName, params) {
  const response = await page.request.get(origin + pathName, {
    params,
    headers: { 'X-Expected-Session': session.session_id },
  });
  assert.equal(response.status(), 200, await response.text());
  return response.json();
}

async function main() {
  assert.ok(domainName && evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const domains = page.getByRole('table', { name: '领域列表' });
    await page.getByRole('button', { name: '新建领域' }).waitFor();
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const root = await save(page, session, {
      request_id: randomUUID(), object_kind: 'domain', action: 'create',
      definition: { name: domainName }, change_note: 'E02-03 合成条目验收',
    });
    const domainId = root.result.object_ref.object_id;
    await page.reload();
    await domains.getByRole('button', { name: domainName }).click();
    await page.getByRole('button', { name: '新建知识成分' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('名称', { exact: true }).fill('等分和单位分数');
    await dialog.getByLabel('含义', { exact: true }).fill('把整体平均分成相同大小的几份。');
    await dialog.getByLabel('适用条件', { exact: true }).fill('各份大小相同。');
    await dialog.getByLabel('正例', { exact: true }).fill('一块纸平均分为四份。');
    await dialog.getByLabel('变更原因').fill('首次收录');
    let dropped;
    await page.route('**' + writePath, async (route) => {
      const response = await route.fetch();
      assert.equal(response.status(), 200, await response.text());
      dropped = (await response.json()).result.object_ref;
      await route.abort();
    }, { times: 1 });
    await dialog.getByRole('button', { name: '保存', exact: true }).click();
    await page.getByText('知识成分已保存。').waitFor();
    assert.ok(dropped);
    const catalog = `/api/m1/domains/${domainId}/objects`;
    const objectPath = `${catalog}/${dropped.object_id}`;
    const first = (await read(page, session, objectPath)).object;
    assert.equal(first.object_ref.version, 1);

    const formula = await save(page, session, {
      request_id: randomUUID(), object_kind: 'kc', action: 'create', domain_id: domainId,
      definition: { ...first.content, name: '四分之一', definition }, change_note: '附结构化公式',
    });
    const formulaPath = `${catalog}/${formula.result.object_ref.object_id}`;
    const originalFormula = (await read(page, session, formulaPath)).object.content.definition;
    await page.getByLabel('按名称查找').fill('四分之一');
    await page.getByRole('button', { name: '查找', exact: true }).click();
    await page.getByRole('button', { name: /四分之一 v1/ }).click();
    const entry = page.getByRole('region', { name: /四分之一/ });
    await entry.locator('math mfrac').waitFor();
    await entry.getByRole('button', { name: '编辑' }).click();
    await dialog.getByText('保留已有内容。').waitFor();
    await dialog.getByLabel('适用条件', { exact: true }).fill('整体必须平均分为四份。');
    await dialog.getByLabel('变更原因').fill('补充条件');
    await dialog.getByRole('button', { name: '保存', exact: true }).click();
    await entry.getByText('整体必须平均分为四份。').waitFor();
    const revised = (await read(page, session, formulaPath)).object;
    assert.equal(revised.object_ref.version, 2);
    assert.deepEqual(revised.content.definition, originalFormula);
    await page.screenshot({ path: path.join(evidence, 'knowledge-detail.png'), fullPage: true });

    await entry.getByRole('button', { name: '移除' }).click();
    await dialog.getByLabel('变更原因').fill('验证移除并保留旧版');
    await dialog.getByRole('button', { name: '确认移除' }).click();
    await page.getByText('已移除', { exact: true }).waitFor();
    await entry.getByLabel('版本', { exact: true }).fill('1');
    await entry.getByRole('button', { name: '查看版本' }).click();
    await entry.getByText('各份大小相同。', { exact: true }).waitFor();
    await entry.locator('math mfrac').waitFor();
    assert.deepEqual((await read(page, session, catalog, { name: '四分之一' })).items, []);
    const old = (await read(page, session, formulaPath, { version: 1 })).object;
    assert.deepEqual(old.content.definition, originalFormula);
    assert.equal(old.is_identity_deleted, true);
    await page.screenshot({ path: path.join(evidence, 'knowledge-history.png'), fullPage: true });
    await writeFile(path.join(evidence, 'results.json'), JSON.stringify({
      domainName, domainId, createRecovered: dropped, updated: revised.object_ref,
      history: old.object_ref, historicalSourceEvent: old.source_event_id,
    }, null, 2));
    console.log('E02-03 browser: lost response recovered, rich content preserved, soft delete and history verified');
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
