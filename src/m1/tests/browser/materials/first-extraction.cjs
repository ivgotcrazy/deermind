// 在部署环境验证缺页处理，并显式启用 C03 的首次真实解析。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const label = process.env.M1_TEST_RICH_DOMAIN_NAME;
const fixture = path.resolve(__dirname, '../../../../mvp_foundation/m1/content-representation/round2/inputs');

async function run() {
  assert.equal(process.env.M1_E02_REAL_MODEL, 'C03');
  assert.ok(label && evidence && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
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
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    const created = await page.request.post(origin + '/api/m1/domain-definitions', {
      data: { request_id: randomUUID(), action: 'create', object_kind: 'domain',
        definition: { name: label }, change_note: 'E02-08 四例验收' }, headers,
    });
    assert.equal(created.status(), 200, await created.text());
    const domain = (await created.json()).result.object_ref;
    await page.getByRole('navigation', { name: '管理功能' }).getByRole('button', { name: '教材管理' }).click();
    await page.getByRole('button', { name: '上传教材' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('所属领域').selectOption(domain.object_id);
    await dialog.getByLabel('教材名称').fill(label);
    await dialog.getByLabel('来源说明').fill('C03 辨错演算原页与局部图');
    await dialog.getByLabel('教材文件').setInputFiles(['C03-0.png', 'C03-1.png'].map((name) => path.join(fixture, name)));
    await dialog.getByRole('button', { name: '上传并登记' }).click();
    await page.getByRole('button', { name: 'C03-0.png' }).waitFor();
    const assistant = page.getByRole('region', { name: '教材助手' });
    await assistant.getByLabel('引用原件').selectOption({ label: 'C03-0.png' });
    await assistant.getByLabel('结束页').fill('2');
    await assistant.getByLabel('给教材助手发消息').fill('请核对第 1–2 页。');
    await assistant.getByRole('button', { name: '发送' }).click();
    await assistant.getByText('等待补充材料。').waitFor({ timeout: 60_000 });

    await assistant.getByLabel('引用原件').selectOption('');
    const receiptResponses = [];
    page.on('response', async (response) => {
      if (response.ok() && response.url().includes('/candidate-batches/')) {
        receiptResponses.push(await response.json());
      }
    });
    await assistant.getByLabel('给教材助手发消息').fill(
      '请解析全部已提供的两张图，只核对这一道辨错题。生成待核对的题目候选，'
      + '保留三行演算及其错误。目录名称可用「分数混合运算」组织本批内容。'
      + '本轮只核对这两张图，请勿等待其他原页。',
    );
    await assistant.getByRole('button', { name: '发送' }).click();
    await page.getByRole('region', { name: '待核对候选' }).waitFor({ timeout: 255_000 });
    assert.equal(receiptResponses.length, 1);
    const result = receiptResponses[0];
    assert.equal(result.batch.decision_state, 'pending');
    assert.ok(result.items.some((entry) => entry.kind === 'task_instance'));
    assert.ok(result.items.every((entry) => entry.source_refs.length > 0));
    await writeFile(path.join(evidence, 'C03-candidate.json'), JSON.stringify(result, null, 2), 'utf8');
    await page.screenshot({ path: path.join(evidence, 'C03-candidate.png'), fullPage: true });
    console.log('E02-08 browser: missing page and a real C03 draft with source references');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
