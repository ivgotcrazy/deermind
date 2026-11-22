// 通过正式 K3s 管理端验证上传、部分失败、收据恢复、补页及原件回读。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, readFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const label = process.env.M1_TEST_RICH_DOMAIN_NAME;

function twoPagePdf() {
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] >>',
  ];
  // 无教材和学生数据，只需要借此验证上传不受普通 2MiB 正文限制。
  let result = '%PDF-1.4\n%' + 'X'.repeat(2 * 1024 * 1024) + '\n';
  const offsets = [0];
  for (const [index, object] of objects.entries()) {
    offsets.push(Buffer.byteLength(result));
    result += `${index + 1} 0 obj\n${object}\nendobj\n`;
  }
  const xref = Buffer.byteLength(result);
  const entries = offsets.slice(1).map((offset) => String(offset).padStart(10, '0') + ' 00000 n \n');
  return Buffer.from(
    result + `xref\n0 5\n0000000000 65535 f \n${entries.join('')}trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`,
  );
}

async function run() {
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
    const makeDomain = await page.request.post(origin + '/api/m1/domain-definitions', {
      data: { request_id: randomUUID(), action: 'create', object_kind: 'domain',
        definition: { name: label }, change_note: 'E02-07 浏览器验收' },
      headers,
    });
    assert.equal(makeDomain.status(), 200, await makeDomain.text());
    const domain = (await makeDomain.json()).result.object_ref;
    const lacking = await page.request.post(origin + '/api/m1/file-uploads', {
      data: { request_id: randomUUID(), purpose: 'material_source', original_name: 'no-domain.pdf',
        declared_media_type: 'application/pdf', declared_byte_size: 10 }, headers,
    });
    assert.equal(lacking.status(), 400);

    await page.getByRole('navigation', { name: '管理功能' }).getByRole('button', { name: '教材管理' }).click();
    await page.getByRole('button', { name: '上传教材' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('所属领域').selectOption(domain.object_id);
    await dialog.getByLabel('教材名称').fill(label);
    await dialog.getByLabel('来源说明').fill('合成验收页');
    const original = twoPagePdf();
    await dialog.getByLabel('教材文件').setInputFiles([
      { name: '验收教材.pdf', mimeType: 'application/pdf', buffer: original },
      { name: '损坏原件.pdf', mimeType: 'application/pdf', buffer: Buffer.from('not a pdf') },
    ]);
    let command;
    let stored;
    await page.route('**/api/m1/material-imports', async (route) => {
      command = route.request().postDataJSON();
      const response = await route.fetch();
      assert.equal(response.status(), 200, await response.text());
      stored = await response.json();
      await route.abort();
    });
    await dialog.getByRole('button', { name: '上传并登记' }).click();
    await page.getByText('已登记 1 份原件。', { exact: false }).waitFor();
    await page.getByRole('status').filter({ hasText: '损坏原件.pdf' }).waitFor();
    await page.unroute('**/api/m1/material-imports');
    assert.ok(command && stored);
    const duplicate = await page.request.post(origin + '/api/m1/material-imports', { data: command, headers });
    assert.equal(duplicate.status(), 200, await duplicate.text());
    assert.deepEqual(await duplicate.json(), stored);
    await page.getByText('2 页 · 顺序 1').waitFor();

    const downloaded = page.waitForEvent('download');
    await page.getByRole('button', { name: '验收教材.pdf' }).click();
    const file = await downloaded;
    await file.saveAs(path.join(evidence, 'roundtrip.pdf'));
    assert.deepEqual(await readFile(path.join(evidence, 'roundtrip.pdf')), original);

    await page.getByRole('button', { name: '补充原件' }).click();
    await dialog.getByLabel('教材文件').setInputFiles({
      name: '附页.png',
      mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg==', 'base64'),
    });
    await dialog.getByRole('button', { name: '上传并登记' }).click();
    await page.getByText('1 页 · 顺序 2').waitFor();
    const current = await page.request.get(origin + '/api/m1/textbooks/' + stored.result.textbook_id, { headers });
    assert.equal(current.status(), 200, await current.text());
    const view = (await current.json()).import;
    assert.equal(view.source_revision, 2);
    assert.equal(view.content_revision, 0);
    assert.equal(view.sources[0].source_ref.id, stored.result.received[0].id);
    const wrongFile = await page.request.get(origin + '/api/m1/resource-files', {
      params: { owner_ref: JSON.stringify(view.sources[0].source_ref), storage_ref: view.sources[1].receipt.storage_ref, view: 'source' },
      headers,
    });
    assert.equal(wrongFile.status(), 404);
    await page.screenshot({ path: path.join(evidence, 'textbook-sources.png'), fullPage: true });
    console.log('E02-07 browser: two-page PDF, bad format, receipt replay, appendix, authorized byte-for-byte read verified');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
