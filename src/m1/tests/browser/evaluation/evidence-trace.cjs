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
    const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await page.getByRole('button', { name: '学习空间', exact: true }).click();
    const target = page.getByRole('row').filter({ hasText: targetTitle });
    await target.getByRole('button').click();
    await page.getByRole('button', { name: '学习目标', exact: true }).click();
    const open = page.getByRole('button', { name: '查看评价证据', exact: true });
    const loaded = page.waitForResponse(
      (response) => response.url().includes('/basis?') && response.ok(),
    );
    await open.first().click();
    const summary = await (await loaded).json();
    assert.equal(summary.view, 'target');
    assert.ok(
      summary.items.some((item) => item.verdict === 'positive'),
      JSON.stringify(summary),
    );
    const dialog = page.getByRole('dialog', { name: '评价证据' });
    await dialog.getByRole('button', { name: '独立 · 正向证据' }).first().click();
    await dialog.getByText('观测概率', { exact: false }).waitFor();
    await dialog.getByRole('button', { name: '查看来源事实' }).first().click();
    const source = dialog.getByRole('region', { name: '来源事实' });
    await source.waitFor();
    assert.match(await source.innerText(), /1\/4|四分之一|1\/5|五分之一/);
    await page.screenshot({ path: path.join(directory, 'evidence-from-target.png') });
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

    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { 'X-Expected-Session': session.session_id };
    const listing = await page.request.get(origin + '/api/m1/learning-spaces', { headers });
    assert.ok(listing.ok(), await listing.text());
    const different = (await listing.json()).items.find(
      (item) => item.target_title !== targetTitle,
    );
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
