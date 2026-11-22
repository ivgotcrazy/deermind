// C03 已采用题目的定义提取与正反归类，沿部署环境的正式受理和收据入口执行。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const label = process.env.M1_TEST_RICH_DOMAIN_NAME;
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;

function paragraph(text) {
  return {
    schema_version: '1', role: 'definition', data_tables: [], source_refs: [],
    blocks: [{
      block_id: 'text', type: 'paragraph',
      provenance: { source_refs: [], transformation: 'generated' },
      payload: { spans: [{ type: 'text', text }] },
    }],
  };
}

async function run() {
  assert.equal(process.env.M1_E02_REAL_MODEL, 'C03');
  assert.ok(label && evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage();
    const api = page.request;
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('navigation', { name: '管理功能' }).waitFor();
    const session = await (await api.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const domains = await (await api.get(origin + '/api/m1/domains', { headers })).json();
    const domain = domains.items.find((item) => item.name === label).object_ref.object_id;
    const base = origin + '/api/m1/domains/' + domain;
    const intake = await (await api.get(base + '/intake-items', { headers })).json();
    const item = intake.items.find((entry) => entry.kind === 'task_instance').item_ref;

    async function saveTask(name, values) {
      const query = new URLSearchParams({ kinds: 'task', name });
      const listed = await (await api.get(base + '/objects?' + query, { headers })).json();
      const existing = listed.items.find((entry) => entry.name === name);
      if (existing) return existing.object_ref;
      const response = await api.post(origin + '/api/m1/domain-definitions', {
        headers, data: {
          request_id: randomUUID(), action: 'create', object_kind: 'task',
          domain_id: domain, change_note: 'E02 C03 归类验收定义',
          definition: { name, ...Object.fromEntries(Object.entries(values).map(([field, text]) => [field, paragraph(text)])) },
        },
      });
      assert.equal(response.status(), 200, await response.text());
      return (await response.json()).result.object_ref;
    }

    const matching = await saveTask('检查分数乘除演算中的错误', {
      responsibility: '核对所给分数乘除运算中每一步，识别错误变形。',
      expected_output: '判断所给算式是否正确，并指出改错的具体步骤。',
      applicability: '给出含除以分数的分数乘除式及作答过程。',
      completion_conditions: '核对题面给定过程并指出把除以分数变成乘以同一个分数的错误。',
      boundaries: '题面必须给出待检查的算式或运算过程。',
    });
    const unrelated = await saveTask('用长、宽、高计算长方体体积', {
      responsibility: '将长、宽、高相乘以求长方体体积。',
      expected_output: '得到有立方单位的体积数值。',
    });
    await mkdir(evidence, { recursive: true });

    async function analysis(endpoint, action, params) {
      const command = { request_id: randomUUID(), intake_item_ref: item, ...params };
      const started = await api.post(base + endpoint, { headers, data: command });
      assert.equal(started.status(), 202, await started.text());
      const accepted = await started.json();
      const same = await api.post(base + endpoint, { headers, data: command });
      assert.deepEqual(await same.json(), accepted);
      const query = new URLSearchParams({
        action, resource_kind: 'domain', resource_id: domain, request_id: command.request_id,
      });
      for (const _ of Array(145)) {
        const response = await api.get(origin + '/api/m1/requests/receipt?' + query, { headers });
        assert.equal(response.status(), 200, await response.text());
        const result = await response.json();
        if (result.receipt_state !== 'accepted') {
          assert.equal(result.receipt_state, 'completed', JSON.stringify(result));
          const read = await api.get(base + '/artifacts/' + result.result.check_ref.id, { headers });
          assert.equal(read.status(), 200, await read.text());
          return result.result;
        }
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      throw new Error('Analysis did not finish within test window');
    }

    const extracted = await analysis('/definition-candidates', 'domain.extract_template', { template_kind: 'task' });
    await writeFile(path.join(evidence, 'C03-extracted-definition.json'), JSON.stringify(extracted, null, 2));
    assert.ok(extracted.proposed_definition?.name || extracted.output.unresolved.length);
    assert.ok(extracted.output.results.length >= 2);
    const positive = await analysis('/classification-checks', 'domain.classify_instance', { task_ref: matching });
    await writeFile(path.join(evidence, 'C03-matching-definition.json'), JSON.stringify(positive, null, 2));
    assert.equal(positive.output.results[0].result, 'matched', JSON.stringify(positive));
    const negative = await analysis('/classification-checks', 'domain.classify_instance', { task_ref: unrelated });
    await writeFile(path.join(evidence, 'C03-mismatched-definition.json'), JSON.stringify(negative, null, 2));
    assert.equal(negative.output.results[0].result, 'mismatch', JSON.stringify(negative));
    console.log('E02-12/13 C03: definition proposal, reuse suggestions and matching/mismatching checks verified');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
