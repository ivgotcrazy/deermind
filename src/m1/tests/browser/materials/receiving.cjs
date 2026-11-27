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
    const lacking = await page.request.post(origin + '/api/m1/file-uploads', {
      data: { request_id: randomUUID(), purpose: 'material_source', original_name: 'no-domain.pdf',
        declared_media_type: 'application/pdf', declared_byte_size: 10 }, headers,
    });
    assert.equal(lacking.status(), 400);

    await page.getByRole('navigation', { name: '管理功能' }).getByRole('button', { name: '教材管理' }).click();
    const domainFilter = page.getByRole('combobox', { name: '按领域查找' });
    assert.equal(await domainFilter.inputValue({ timeout: 5000 }), '');
    await page.getByRole('button', { name: '上传教材' }).click();
    const dialog = page.getByRole('dialog', { name: '上传教材', exact: true });
    const owner = dialog.getByRole('combobox', { name: /所属领域/ });
    assert.equal(await owner.inputValue(), '');
    assert.ok(await dialog.getByRole('button', { name: '上传并解析' }).isDisabled());
    await dialog.getByLabel('教材名称').fill(label);
    await dialog.getByLabel('来源说明').fill('合成验收页');
    const original = twoPagePdf();
    await dialog.getByLabel('教材文件').setInputFiles([
      { name: '验收教材.pdf', mimeType: 'application/pdf', buffer: original },
      { name: '损坏原件.pdf', mimeType: 'application/pdf', buffer: Buffer.from('not a pdf') },
    ]);
    const create = dialog.getByRole('button', { name: '新建领域' });
    const domainEditor = page.getByRole('dialog', { name: '新建所属领域' });
    const domainName = '小学数学 · ' + label;
    await create.click();
    await domainEditor.getByRole('button', { name: '取消' }).click();
    assert.equal(await dialog.getByLabel('教材名称').inputValue(), label);
    await create.click();
    await domainEditor.getByLabel('领域名称').fill(domainName);
    await domainEditor.getByLabel('覆盖范围（选填）').fill('测试教材');
    await domainEditor.getByLabel('领域说明（选填）').fill('教材导入交互验收');
    await page.screenshot({ path: path.join(evidence, 'textbook-create-domain.png') });
    const created = page.waitForResponse((response) => response.url().endsWith('/domain-definitions') && response.ok());
    await domainEditor.getByRole('button', { name: '创建并选用' }).click();
    const domain = (await (await created).json()).result.object_ref;
    await owner.locator('option:checked').filter({ hasText: domainName }).waitFor({ state: 'attached' });
    assert.equal(await owner.inputValue(), domain.object_id);
    assert.equal(await dialog.getByLabel('教材文件').evaluate((input) => input.files.length), 2);
    const domainView = await page.request.get(origin + '/api/m1/domains/' + domain.object_id + '/objects/' + domain.object_id, { headers });
    assert.ok(domainView.ok());
    const content = (await domainView.json()).object.content;
    assert.equal(content.coverage.blocks[0].payload.spans[0].text, '测试教材');
    assert.equal(content.description.blocks[0].payload.spans[0].text, '教材导入交互验收');
    let command;
    let stored;
    await page.route('**/api/m1/material-imports', async (route) => {
      command = route.request().postDataJSON();
      const response = await route.fetch();
      assert.equal(response.status(), 200, await response.text());
      stored = await response.json();
      await route.abort();
    });
    await dialog.getByRole('button', { name: '上传并解析' }).click();
    await page.getByText('已登记 1 份原件。', { exact: false }).waitFor();
    await page.getByRole('status').filter({ hasText: '损坏原件.pdf' }).waitFor();
    await page.unroute('**/api/m1/material-imports');
    assert.ok(command && stored);
    const duplicate = await page.request.post(origin + '/api/m1/material-imports', { data: command, headers });
    assert.equal(duplicate.status(), 200, await duplicate.text());
    assert.deepEqual(await duplicate.json(), stored);
    await page.getByRole('button', { name: '教材原件', exact: true }).click();
    await page.getByText('2 页 · 顺序 1').waitFor();
    const workspace = page.getByRole('region', { name: '教材管理' });
    await workspace.getByText('所属领域 · ' + domainName, { exact: false }).waitFor();

    const downloaded = page.waitForEvent('download');
    await page.getByRole('button', { name: '验收教材.pdf' }).click();
    const file = await downloaded;
    await file.saveAs(path.join(evidence, 'roundtrip.pdf'));
    assert.deepEqual(await readFile(path.join(evidence, 'roundtrip.pdf')), original);

    await page.getByRole('button', { name: '补充原件' }).click();
    const appendix = page.getByRole('dialog', { name: '补充原件' });
    await appendix.getByLabel('教材文件').setInputFiles({
      name: '附页.png',
      mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg==', 'base64'),
    });
    await appendix.getByRole('button', { name: '补充原件' }).click();
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
    await page.getByRole('button', { name: '返回教材列表' }).click();
    await domainFilter.selectOption(domain.object_id);
    const nameSearch = page.getByRole('searchbox', { name: '教材名称' });
    const table = workspace.getByRole('table', { name: '教材列表' });
    await table.getByRole('button', { name: label, exact: true }).waitFor();
    await table.getByRole('columnheader', { name: '所属领域' }).waitFor();
    assert.equal(await table.locator('tbody tr').count(), 1);
    await nameSearch.fill('no-match-' + label);
    await workspace.getByText('没有符合条件的教材。').waitFor();
    await nameSearch.fill(label);
    await table.getByRole('cell', { name: domainName, exact: true }).waitFor();
    await table.getByRole('button', { name: label, exact: true }).click();
    await page.getByRole('button', { name: '返回教材列表' }).click();
    assert.equal(await nameSearch.inputValue(), label);
    assert.equal(await domainFilter.inputValue(), domain.object_id);
    await page.getByRole('button', { name: '上传教材' }).click();
    assert.equal(await owner.inputValue(), domain.object_id);
    assert.equal(await dialog.getByLabel('教材文件').evaluate((input) => input.files.length), 0);
    await page.screenshot({ path: path.join(evidence, 'textbook-domain-upload.png') });
    await dialog.getByRole('button', { name: '取消' }).click();
    await nameSearch.fill('从其他领域查找同名教材');
    const otherDomain = await domainFilter.locator('option').evaluateAll((options, id) =>
      options.map((option) => option.value).find((value) => value && value !== id), domain.object_id);
    if (otherDomain) {
      await domainFilter.selectOption(otherDomain);
      await nameSearch.fill(label);
      await workspace.getByText('没有符合条件的教材。').waitFor();
    }
    await nameSearch.fill('');
    await domainFilter.selectOption('');
    await table.getByRole('button').first().waitFor();
    await page.screenshot({ path: path.join(evidence, 'textbook-domain-list.png') });
    console.log('Verified domain filtering, inline domain creation, upload and receipt recovery, detail, retained filters, appendix and source download.');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
