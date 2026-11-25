// Exercise the deployed target manager without creating textbooks or learning targets.
const assert = require('node:assert/strict');
const { mkdir, readFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

async function run() {
  const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
  const directory = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
  const fixture = JSON.parse(await readFile(process.env.M1_TEST_TARGET_FIXTURE, 'utf8'));
  await mkdir(directory, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const capture = (name) => page.screenshot({ path: path.join(directory, name + '.png') });
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码', { exact: true }).fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await page
      .getByRole('navigation', { name: '管理功能' })
      .getByRole('button', { name: '目标管理' })
      .click();

    const area = page.getByRole('region', { name: '目标管理', exact: true });
    const domain = area.getByLabel('领域', { exact: true });
    const book = area.getByLabel('教材', { exact: true });
    const create = area.getByRole('button', { name: '新建目标', exact: true });
    const list = area.getByRole('table', { name: '已保存的学习目标' });
    const back = area.getByRole('button', { name: '返回学习目标列表' });
    await area.getByText('请先选择领域和教材。').waitFor();
    assert.equal(await domain.inputValue(), '');
    assert.ok((await book.isDisabled()) && (await create.isDisabled()));
    await capture('target-initial');

    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    async function read(route) {
      const response = await page.request.get(origin + '/api/m1' + route, {
        headers: { 'X-Expected-Session': session.session_id },
      });
      assert.ok(response.ok(), route + ' ' + response.status());
      return response.json();
    }
    const textbook = (await read('/textbooks/' + fixture.textbook_id)).import.textbook;
    const catalog = await read('/textbooks?domain_id=' + textbook.domain_id + '&limit=100');
    await domain.selectOption(textbook.domain_id);
    await book.locator('option').nth(catalog.items.length).waitFor({ state: 'attached' });
    assert.deepEqual(
      await book.locator('option').evaluateAll((rows) => rows.slice(1).map((row) => row.value)),
      catalog.items.map((row) => row.textbook_id),
    );
    if (catalog.items.length === 1) assert.equal(await book.inputValue(), fixture.textbook_id);
    else await book.selectOption(fixture.textbook_id);
    await list.waitFor();
    await capture('target-scoped-list');

    const domainName = await domain.locator('option:checked').innerText();
    const textbookName = await book.locator('option:checked').innerText();
    const title = await list.getByRole('button').first().innerText();
    for (const [button, heading] of [
      [list.getByRole('button').first(), title],
      [create, '新建目标'],
    ]) {
      await button.click();
      await area.getByRole('heading', { name: heading, exact: true }).waitFor();
      const breadcrumb = await area.locator('.target-breadcrumb').innerText();
      assert.ok(breadcrumb.includes(domainName.trim()) && breadcrumb.includes(textbookName.trim()));
      assert.equal(
        await area.getByRole('region', { name: '活动 Prompt 配置' }).getByRole('combobox').count(),
        4,
      );
      if (heading === '新建目标') await capture('target-create');
      await back.click();
      assert.equal(await domain.inputValue(), textbook.domain_id);
      assert.equal(await book.inputValue(), fixture.textbook_id);
      await list.waitFor();
    }

    const other = (
      await domain.locator('option').evaluateAll((rows) => rows.map((row) => row.value))
    ).find((id) => id && id !== textbook.domain_id);
    assert.ok(other, 'A second test domain is required to verify switching');
    const otherCatalog = await read('/textbooks?domain_id=' + other + '&limit=100');
    await domain.selectOption(other);
    if (!otherCatalog.items.length) {
      await area.getByText('该领域暂无教材。').waitFor();
      assert.ok((await book.isDisabled()) && (await create.isDisabled()));
      assert.equal(await list.count(), 0);
      await capture('target-empty-domain');
    }

    // Provide two paginated choices and an empty target list without writing fixture data.
    await domain.selectOption('');
    await page.route('**/api/m1/textbooks?**', (route) => {
      const query = new URL(route.request().url()).searchParams;
      if (query.get('domain_id') !== textbook.domain_id) return route.continue();
      const second = query.has('cursor');
      const row = second
        ? { ...textbook, textbook_id: '00000000-0000-4000-8000-000000000002' }
        : textbook;
      return route.fulfill({ json: { items: [row], next_cursor: second ? null : 'p2' } });
    });
    await page.route('**/api/m1/learning-targets?**', (route) =>
      route.fulfill({ json: { items: [] } }),
    );
    await domain.selectOption(textbook.domain_id);
    await area.getByText('请选择教材，查看该教材的学习目标。').waitFor();
    assert.equal(await book.locator('option').count(), 3);
    assert.equal(await book.inputValue(), '');
    assert.ok(await create.isDisabled());
    await book.selectOption(fixture.textbook_id);
    await area.getByText('这本教材还没有学习目标。').waitFor();
    assert.ok(await create.isEnabled());
    console.log('Target selection, scoped navigation, empty states and paginated choices passed.');
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
