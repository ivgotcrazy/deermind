// 在已部署的管理端建立两种方法及先导，验证按方法查看的实际关系。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const domainName = process.env.M1_TEST_RICH_DOMAIN_NAME;

function textBody(text) {
  return {
    schema_version: '1', role: 'definition', source_refs: [], data_tables: [],
    blocks: [{
      block_id: 'p1', type: 'paragraph', payload: { spans: [{ type: 'text', text }] },
      provenance: { transformation: 'generated', source_refs: [], note: '' },
    }],
  };
}

async function save(page, session, kind, definition, domainId) {
  const response = await page.request.post(origin + '/api/m1/domain-definitions', {
    data: {
      request_id: randomUUID(), action: 'create', object_kind: kind, definition,
      ...(domainId ? { domain_id: domainId } : {}), change_note: 'E02-05 浏览器验收',
    },
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
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error.name));
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('button', { name: '新建领域' }).waitFor();
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const root = await save(page, session, 'domain', { name: domainName });
    const domainId = root.object_id;
    for (const name of ['分数的意义', '求一个数的几分之几', '同一参照量的分率相加']) {
      await save(page, session, 'kc', {
        name, definition: textBody(name), applicability: textBody('可确定参照整体。'),
      }, domainId);
    }
    await save(page, session, 'task', { name: '识别参照整体' }, domainId);
    await page.reload();
    await page.getByRole('table', { name: '领域列表' }).getByRole('button', { name: domainName }).click();
    const navigation = page.getByRole('navigation', { name: '领域对象' });
    await navigation.getByRole('button', { name: '方法', exact: true }).click();
    const dialog = page.getByRole('dialog');

    async function createMethod(name, process, refs) {
      await page.getByRole('button', { name: '新建方法' }).click();
      await dialog.getByLabel('名称', { exact: true }).fill(name);
      await dialog.getByLabel('方法思路', { exact: true }).fill(process);
      await dialog.getByLabel('关键过程', { exact: true }).fill(process);
      for (const ref of refs) {
        await dialog.getByLabel('选择知识成分').selectOption({ label: `${ref} · v1` });
        await dialog.getByRole('button', { name: '关联知识成分', exact: true }).click();
      }
      await dialog.getByLabel('变更原因').fill('保存方法');
      await dialog.getByRole('button', { name: '保存', exact: true }).click();
      const detail = page.getByRole('region', { name: new RegExp(name) });
      for (const ref of refs) await detail.getByText(`${ref} · v1`, { exact: true }).waitFor();
    }

    await createMethod('先求增加量', '用原量乘四分之一，再加回原量。', ['分数的意义', '求一个数的几分之几']);
    await createMethod('直接乘新比例', '把原量看作一份，新量是原量的四分之五。', ['同一参照量的分率相加']);
    await navigation.getByRole('button', { name: '任务', exact: true }).click();
    await page.getByRole('button', { name: '新建任务' }).click();
    await dialog.getByLabel('名称', { exact: true }).fill('增加四分之一');
    await dialog.getByLabel('认知责任', { exact: true }).fill('计算增加后的数量并说明依据。');
    for (const method of ['先求增加量', '直接乘新比例']) {
      await dialog.getByLabel('选择方法').selectOption({ label: `${method} · v1` });
      await dialog.getByRole('button', { name: '关联方法', exact: true }).click();
    }
    await dialog.getByLabel('选择先导任务').selectOption({ label: '识别参照整体 · v1' });
    await dialog.getByRole('button', { name: '添加先导' }).click();
    await dialog.getByLabel('先导理由').fill('先辨认增加比例所指的原量。');
    await dialog.getByLabel('适用范围').selectOption('specified');
    await dialog.getByRole('checkbox', { name: '先求增加量 · v1' }).check();
    await dialog.getByLabel('变更原因').fill('关联两种方法和指定先导');
    await dialog.getByRole('button', { name: '保存', exact: true }).click();
    const task = page.getByRole('region', { name: /增加四分之一/ });
    const scope = task.getByRole('region', { name: '任务关系' });
    const filter = scope.getByLabel('查看方法');
    await scope.getByText('识别参照整体 · v1', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(evidence, 'task-relations.png'), fullPage: true });
    await filter.selectOption({ label: '直接乘新比例 · v1' });
    await scope.getByText('同一参照量的分率相加 · v1（直接乘新比例 · v1）', { exact: true }).waitFor();
    await scope.getByText('识别参照整体 · v1', { exact: true }).waitFor({ state: 'hidden' });
    assert.equal(await scope.getByText('分数的意义', { exact: false }).count(), 0);
    assert.equal(pageErrors.length, 0);
    await page.screenshot({ path: path.join(evidence, 'filtered-relations.png'), fullPage: true });
    await writeFile(path.join(evidence, 'results.json'), JSON.stringify({ domainName, domainId }, null, 2));
    console.log('E02-05 browser: two methods, direct knowledge, scoped prerequisite and filters verified');
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
