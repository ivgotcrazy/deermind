const assert = require('node:assert/strict');
const { mkdir } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
const directory = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const targetTitle = process.env.M1_TEST_EVIDENCE_TARGET;

async function run() {
  assert.ok(origin && directory && targetTitle);
  await mkdir(directory, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE,
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const capture = (name) =>
      page.screenshot({ path: path.join(directory, name + '.png'), animations: 'disabled' });
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await page.getByRole('table', { name: '领域列表' }).waitFor();
    await capture('domain-list');
    const nav = page.getByRole('navigation', { name: '管理功能' });
    await nav.getByRole('button', { name: '目标管理' }).click();
    const book = page.getByLabel('教材', { exact: true });
    assert.ok(await book.isDisabled());
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { 'X-Expected-Session': session.session_id };
    const spaces = await page.request.get(origin + '/api/m1/learning-spaces', { headers });
    assert.ok(spaces.ok());
    const spaceRows = (await spaces.json()).items;
    const fixtureSpace = spaceRows.find((space) => space.target_title === targetTitle);
    assert.ok(fixtureSpace, 'The evidence fixture must have a visible learning space');
    const detail = await page.request.get(origin + '/api/m1/textbooks/' + fixtureSpace.textbook_id, {
      headers,
    });
    assert.ok(detail.ok());
    const fixtureBook = (await detail.json()).import.textbook;
    await page.getByLabel('领域', { exact: true }).selectOption(fixtureBook.domain_id);
    await book.locator('option').nth(1).waitFor({ state: 'attached' });
    await book.selectOption(fixtureBook.textbook_id);
    await page.getByRole('table', { name: '已保存的学习目标' }).waitFor();
    await capture('target-list');
    await nav.getByRole('button', { name: '学习空间', exact: true }).click();
    const target = page.getByRole('row').filter({ hasText: targetTitle });
    await target.waitFor();
    await capture('space-list');
    await target.getByRole('button').click();
    await page.getByRole('button', { name: '学习目标', exact: true }).click();
    const open = page.getByRole('button', { name: '查看评价证据', exact: true });
    const loaded = page.waitForResponse(
      (response) => response.url().includes('/basis?') && response.ok(),
    );
    await open.first().waitFor();
    await capture('A04');
    await open.first().click();
    const summary = await (await loaded).json();
    assert.equal(summary.view, 'target');
    assert.ok(
      summary.items.some((item) => item.verdict === 'positive'),
      JSON.stringify(summary),
    );
    const dialog = page.getByRole('dialog', { name: '评价证据' });
    const entry = dialog.getByRole('button', { name: '独立 · 正向证据' }).first();
    await entry.waitFor();
    const frame = await dialog.boundingBox();
    assert.ok(frame && frame.x === 892 && frame.y === 60 && frame.width === 548);
    const entryId = await entry.getAttribute('data-evidence');
    const chosen = summary.items.find((item) => item.evidence_ref.id === entryId);
    assert.equal(chosen.source_activity, 'detection');
    assert.ok(chosen.source_event_refs.includes(chosen.timed_event_id));
    const chosenRow = dialog.locator('.trace-list > div').filter({
      has: page.locator(`[data-evidence="${entryId}"]`),
    });
    assert.equal(await chosenRow.locator('time').getAttribute('datetime'), chosen.occurred_at);
    assert.match(await chosenRow.innerText(), /正式检测/);
    await capture('A05');
    await entry.click();
    await dialog.getByText('观测概率', { exact: false }).waitFor();
    await capture('A06');
    await dialog.getByRole('button', { name: '查看原始作答' }).click();
    const source = dialog.getByRole('region', { name: '来源事实' });
    await source.waitFor();
    assert.match(await source.innerText(), /1\/4|四分之一|1\/5|五分之一/);
    await source.locator('[data-role="statement"]').waitFor();
    assert.ok((await source.locator('.origin-text').innerText()).length > 0);
    const sourceTime = source.locator('time');
    assert.equal(await sourceTime.getAttribute('datetime'), chosen.occurred_at);
    assert.equal(
      await sourceTime.innerText(),
      new Intl.DateTimeFormat('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
        timeZone: 'Asia/Shanghai',
      }).format(new Date(chosen.occurred_at)),
    );
    await capture('A07');
    const otherSource = dialog.getByRole('button', { name: /查看来源事实/ }).first();
    const readOther = page.waitForResponse(
      (response) =>
        response.url().includes('/basis?') && response.url().includes('event_id=') && response.ok(),
    );
    await otherSource.click();
    const other = await (await readOther).json();
    assert.notEqual(other.source.event_id, chosen.timed_event_id);
    await source.getByText('原始题面', { exact: true }).waitFor();
    assert.equal(await source.locator('time').count(), 0);
    await dialog.getByRole('button', { name: '返回证据列表' }).click();
    assert.ok(await entry.evaluate((el) => el === document.activeElement));
    await dialog.getByRole('button', { name: '关闭', exact: true }).click();

    await page.getByRole('button', { name: '空间事件', exact: true }).click();
    await page.getByLabel('事件类型').selectOption('AnswerSubmitted');
    const eventRow = page.getByRole('row').filter({ hasText: '提交作答' }).last();
    const traced = page.waitForResponse(
      (response) => response.url().includes('/basis?') && response.ok(),
    );
    await eventRow.getByRole('button', { name: '查看相关证据' }).click();
    const reverse = await (await traced).json();
    assert.equal(reverse.view, 'event');
    assert.ok(reverse.items.length);
    await page.screenshot({ path: path.join(directory, 'evidence-from-event.png') });

    const targetRead = new URL((await loaded).url());
    targetRead.search = new URLSearchParams({
      view: 'event',
      event_id: summary.items[0].source_event_refs[0],
    }).toString();
    const sameSource = await page.request.get(targetRead.toString(), { headers });
    assert.ok(sameSource.ok());
    assert.ok(
      (await sameSource.json()).items.some(
        (item) => item.evidence_ref.id === summary.items[0].evidence_ref.id,
      ),
    );
    const different = spaceRows.find((item) => item.target_title !== targetTitle);
    assert.ok(different, 'The cluster fixture must include another learning space');
    const wrongScope = new URL(
      '/api/m1/evaluation/spaces/' + different.space_id + '/basis',
      origin,
    );
    wrongScope.searchParams.set('view', 'evidence');
    wrongScope.searchParams.set('evidence_id', summary.items[0].evidence_ref.id);
    const forbidden = await page.request.get(wrongScope.toString(), { headers });
    assert.equal(forbidden.status(), 404);
    console.log(
      'Verified target, evidence, original fact, event reverse lookup and cross-space 404.',
    );
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
