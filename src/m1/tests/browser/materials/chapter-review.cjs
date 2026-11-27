// 在目标集群验证五页教材的上传顺序、跨页归属、定点修订、采用和领域交接。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

async function chapterScans(page) {
  const images = await page.evaluate(() => {
    const pages = [
      ['路程指物体运动所经过的路径长度。'],
      ['速度表示单位时间内通过的路程。'],
      ['匀速运动的路程等于速度乘以时间。'],
      ['例题 小车每分钟行驶 2 米，行驶 3 分钟。'],
      ['接上页例题：小车一共行驶多少米？', '解法一：2 + 2 + 2 = 6（米）。', '解法二：2 × 3 = 6（米）。'],
    ];
    return pages.map((lines, i) => {
      const canvas = document.createElement('canvas');
      canvas.width = 820;
      canvas.height = 550;
      const context = canvas.getContext('2d');
      context.fillStyle = 'white';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = 'black';
      context.font = '28px "Microsoft YaHei", sans-serif';
      context.fillText('第一章 匀速运动', 30, 60);
      lines.forEach((text, n) => context.fillText(text, 30, 180 + 48 * n));
      context.fillText(String(i + 1), 390, 500);
      return canvas.toDataURL('image/png').split(',')[1];
    });
  });
  return [1, 2, 3, 5, 4].map(n => ({
    name:`chapter-${n}.png`,mimeType:'image/png',buffer:Buffer.from(images[n-1],'base64'),
  }));
}

async function run() {
  const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
  const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
  assert.ok(evidence);
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 920 } });
    const exceptions = [];
    page.on('pageerror', (error) => exceptions.push(error.message));
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const menu = page.getByRole('navigation', { name: '管理功能' });
    await menu.waitFor();
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = {
      Origin: origin,
      'X-Expected-Session': session.session_id,
      'X-CSRF-Token': session.csrf_token,
    };
    const title = '整章浏览器验收 ' + randomUUID().slice(0, 8);
    async function define(object_kind, definition, domain_id) {
      const response = await page.request.post(origin + '/api/m1/domain-definitions', {
        headers,
        data: {
          request_id: randomUUID(),
          action: 'create',
          object_kind,
          definition,
          domain_id,
          change_note: '合成教材验收',
        },
      });
      assert.ok(response.ok(), await response.text());
      return (await response.json()).result.object_ref;
    }
    const domain = await define('domain', { name: title });
    const method = await define('solution', { name: '用速度乘时间' }, domain.object_id);
    const task = await define('task', { name: '求路程', method_refs: [method] }, domain.object_id);
    await menu.getByRole('button', { name: '教材管理' }).click();
    await page.getByRole('button', { name: '上传教材' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('所属领域').selectOption(domain.object_id);
    await dialog.getByLabel('教材名称').fill(title);
    await dialog.getByLabel('来源说明').fill('五页合成教材');
    await dialog.getByLabel('教材文件').setInputFiles(await chapterScans(page));
    await dialog.getByRole('listitem').last().getByRole('button', { name: '上移' }).click();
    assert.match(await dialog.getByRole('listitem').nth(3).innerText(), /chapter-4/);
    const stored = page.waitForResponse(
      (r) => r.request().method() === 'POST' && r.url().endsWith('/material-imports'),
    );
    await dialog.getByRole('button', { name: '上传并解析' }).click();
    const book = (await (await stored).json()).result;
    await page.getByRole('button', { name: '候选与领域入库', exact: true }).click();
    const review = page.getByRole('region', { name: '待核对候选' });
    const adopt = review.getByRole('button', { name: '采用', exact: true });
    await adopt.waitFor({ timeout: 300_000 });
    const family = review
      .locator('.review-family')
      .filter({ has: page.locator('h4 small', { hasText: '题目' }) });
    assert.equal(await family.count(), 1);
    assert.equal(await family.locator('article.solution').count(), 2);
    await family
      .getByRole('button', { name: /查看原页/ })
      .first()
      .click();
    await page.getByRole('dialog', { name: '来源原页' }).locator('img').waitFor();
    await page.getByRole('button', { name: '关闭原页' }).click();
    await family.getByRole('button', { name: '引用此项纠错' }).first().click();
    await page
      .getByLabel('给教材助手发消息')
      .fill('请将所选题目的标题改为“小车行驶的路程（修订）”，只修改标题。');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await review.getByText('已修改 · 对照修订前内容').waitFor({ timeout: 300_000 });
    await review.getByText('已修改 · 对照修订前内容').click();
    await page.screenshot({ path: path.join(evidence, 'chapter-review.png'), fullPage: true });
    await adopt.click();
    const adopted = page.getByRole('region', { name: '已采用内容' });
    const checkbox = adopted.getByRole('checkbox', { name: /题目 · 小车/ });
    await checkbox.check();
    await adopted.getByRole('button', { name: '提交领域入库' }).click();
    await adopted.getByText('领域已接收', { exact: true }).waitFor({ timeout: 65_000 });
    await page.getByRole('button', { name: '章节关联', exact: true }).click();
    await page.getByRole('button', { name: '添加关联' }).click();
    const editor = page.getByRole('dialog');
    await editor.getByRole('combobox').selectOption(task.object_id);
    await editor.getByRole('checkbox', { name: /用速度乘时间/ }).check();
    await editor.getByRole('button', { name: '保存' }).click();
    await page
      .getByRole('row')
      .filter({ hasText: '求路程' })
      .getByText(/用速度乘时间/)
      .waitFor();
    await page.getByRole('button', { name: '返回教材列表' }).click();
    await page.getByRole('searchbox', { name: '教材名称' }).fill(title);
    const row = page.getByRole('row').filter({ hasText: title });
    await row.getByText('教材已采用', { exact: true }).waitFor();
    await row.getByRole('button', { name: '查看教材' }).click();
    await page.getByRole('button', { name: '候选与领域入库', exact: true }).click();
    await adopted.getByText('领域已接收', { exact: true }).waitFor();
    await page.setViewportSize({ width: 820, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({ path: path.join(evidence, 'chapter-narrow.png'), fullPage: true });
    assert.deepEqual(exceptions, []);
    await writeFile(
      path.join(evidence, 'browser.json'),
      JSON.stringify(
        {
          title,
          book: book.textbook_id,
          domain: domain.object_id,
          task: task.object_id,
          method: method.object_id,
          exceptions,
        },
        null,
        2,
      ),
    );
    console.log(
      'PASS: upload, reorder, five pages, one question and two methods, source preview, correction, adoption, intake, chapter association, reopen',
    );
  } finally {
    await browser.close();
  }
}
run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
