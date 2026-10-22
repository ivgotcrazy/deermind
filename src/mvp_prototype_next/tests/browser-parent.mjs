// M07: retained parent UI, scoped local persistence and read-only record workflow.
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { once } from 'node:events';
import path from 'node:path';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const repo = fileURLToPath(new URL('../../../', import.meta.url));
const output = path.join(repo, '.tmp/mvp-prototype-next/m07');
await mkdir(output, { recursive: true });
const manifest = JSON.parse(await readFile(new URL('../parent/BASELINE_MANIFEST.json', import.meta.url), 'utf8'));
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
for (const item of manifest.files) {
  assert.equal(digest(await readFile(path.join(repo, item.source))), item.sha256, `Source changed: ${item.source}`);
  const bytes = await readFile(path.join(repo, item.destination));
  if (!item.destination.endsWith('/state.ts')) assert.equal(digest(bytes), item.sha256, `Parent baseline changed: ${item.destination}`);
  else {
    const original = (await readFile(path.join(repo, item.source), 'utf8')).replaceAll('\r\n', '\n');
    const restored = bytes.toString().replaceAll('\r\n', '\n')
      .replace('// Keep retained parent data separate from both the old origin and the new V2 student store.\n', '')
      .replace("const key='deermind-next-parent-v1';", "const key='deermind-structure-v1';");
    assert.equal(restored, original, 'Only the local storage namespace is adapted');
  }
}
let calls = 0;
const server = createPrototypeServer({ config: { key: 'fixture', model: 'fixed' }, provider: async () => { calls++; throw Error('Parent must not call the student model'); } });
server.listen(0, '127.0.0.1'); await once(server, 'listening');
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
const errors = [], requests = [], comparisons = [];
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(12000);
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => { if (request.url().includes('/api/')) requests.push(request.url()); });
const input = () => page.getByLabel('家长咨询输入', { exact: true });
const stored = () => page.evaluate(() => JSON.parse(localStorage.getItem('deermind-next-parent-v1')));
const navigate = async route => { await page.goto(`${base}/parent/#/${route}`); await input().waitFor(); };
try {
  // Navigation and storage tests use an isolated browser, never the user's local data.
  await page.goto(base + '/parent/'); await input().waitFor();
  assert.ok(page.url().endsWith('#/overview'));
  await page.evaluate(() => { localStorage.setItem('deermind-next-workspace-v1', '{"m07Sentinel":true}'); localStorage.setItem('deermind-structure-v1', '{"oldSentinel":true}'); });
  await input().fill('林同学校内草稿');
  await page.getByLabel('当前孩子', { exact: true }).selectOption('S0042');
  assert.equal(await input().inputValue(), '');
  await input().fill('周同学校内草稿');
  await page.getByLabel('当前学习空间', { exact: true }).selectOption('external');
  assert.equal(await input().inputValue(), '');
  await page.getByRole('heading', { name: '还没有本空间的学习评价' }).waitFor();
  await input().fill('周同学校外草稿');
  await page.reload(); await input().waitFor();
  assert.equal(await input().inputValue(), '周同学校外草稿');
  await page.getByLabel('当前学习空间', { exact: true }).selectOption('school');
  assert.equal(await input().inputValue(), '周同学校内草稿');
  await page.getByLabel('当前孩子', { exact: true }).selectOption('S0001');
  assert.equal(await input().inputValue(), '林同学校内草稿');
  const initialCounts = await page.locator('.counts').allTextContents();
  await page.getByRole('button', { name: '咨询', exact: true }).click();
  await input().fill('希望了解为什么需要加强。');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  assert.equal(await input().inputValue(), '');
  await page.getByRole('button', { name: '对话历史', exact: true }).click();
  await page.getByText('希望了解为什么需要加强。', { exact: true }).waitFor();
  await page.reload(); await input().waitFor();
  await page.getByRole('button', { name: '对话历史', exact: true }).click();
  await page.getByText('希望了解为什么需要加强。', { exact: true }).waitFor();
  assert.equal((await stored()).sessions.length, 0, 'Consultation cannot create a student performance');
  await page.getByRole('button', { name: '概况', exact: true }).click();
  assert.deepEqual(await page.locator('.counts').allTextContents(), initialCounts);
  await page.locator('.chapter-row').filter({ hasText: '分数的应用' }).click();
  await page.getByRole('heading', { name: '分数的应用 · 具体要求', exact: true }).waitFor();
  await page.getByRole('button', { name: '查看本章记录示例', exact: true }).first().click();
  const recordUrl = page.url(), answer = await page.locator('blockquote').innerText();
  assert.equal(await page.getByRole('button', { name: '回到本章讲解', exact: true }).count(), 0);
  await page.getByRole('button', { name: '提出复核', exact: true }).click();
  await page.getByLabel('复核说明').fill('希望复核帮助条件是否记录完整。');
  await page.getByRole('button', { name: '提交复核事项', exact: true }).click();
  assert.equal(await page.locator('blockquote').innerText(), answer);
  const issue = (await stored()).issues[0];
  assert.equal(issue.learner, 'S0001'); assert.equal(issue.space, 'school'); assert.equal(issue.status, '待复核');
  assert.ok(!JSON.stringify(issue).includes('希望了解为什么需要加强。'), 'Private consultation must not accompany the review');
  await page.reload(); await input().waitFor();
  await page.getByText(issue.id, { exact: true }).waitFor();
  await page.getByLabel('当前孩子', { exact: true }).selectOption('S0042');
  await page.goto(recordUrl); await page.getByRole('heading', { name: '当前范围内没有这条内容' }).waitFor();
  await page.getByLabel('当前孩子', { exact: true }).selectOption('S0001');
  await page.getByLabel('当前学习空间', { exact: true }).selectOption('external');
  await page.goto(recordUrl); await page.getByRole('heading', { name: '当前范围内没有这条内容' }).waitFor();
  for (const route of ['lesson?id=fake', 'prepare?id=fake', 'materials', 'records']) {
    await navigate(route); await page.getByRole('heading', { name: '当前范围内没有这条内容' }).waitFor();
  }
  await page.getByLabel('当前学习空间', { exact: true }).selectOption('school');
  await page.getByRole('button', { name: '查看课堂进度', exact: true }).click();
  assert.equal(await page.getByRole('button', { name: '保存课堂进度', exact: true }).count(), 0);
  await page.getByRole('button', { name: '关闭', exact: true }).click();
  await page.locator('.brand').click(); await input().waitFor();
  assert.ok(page.url().includes('/parent/structure.html?role=parent#/overview'));
  await page.getByRole('button', { name: '账号与关系', exact: true }).click();
  await page.getByRole('heading', { name: '账号与关系', exact: true }).waitFor();
  const untouched = await page.evaluate(() => [localStorage.getItem('deermind-next-workspace-v1'), localStorage.getItem('deermind-structure-v1')]);
  assert.deepEqual(untouched, ['{"m07Sentinel":true}', '{"oldSentinel":true}']);
  await page.getByLabel('评审视角').selectOption('admin'); await page.waitForURL(base + '/admin/');
  assert.equal((await fetch(base + '/parent/src/structure/state.ts')).status, 404);
  assert.equal(calls, 0); assert.deepEqual(requests, []); assert.deepEqual(errors, []);

  // Optional pixel and text comparison with the preserved old running parent app.
  if (process.argv.includes('--compare-legacy')) {
    for (const viewport of [{ width: 1280, height: 900 }, { width: 430, height: 932 }]) {
      const clean = await browser.newContext({ viewport });
      const old = await clean.newPage(), next = await clean.newPage();
      for (const route of ['overview', 'status?chapter=fractions', 'record?id=R-S0001-2', 'consult', 'account']) {
        await old.goto(`http://127.0.0.1:5178/structure.html?role=parent#/${route}`);
        await next.goto(`${base}/parent/#/${route}`);
        await old.getByLabel('家长咨询输入', { exact: true }).waitFor(); await next.getByLabel('家长咨询输入', { exact: true }).waitFor();
        assert.equal(await next.locator('.wireframe').innerText(), await old.locator('.wireframe').innerText(), `Visible text changed: ${route}`);
        const name = `${viewport.width}-${route.split('?')[0]}`;
        const before = await old.screenshot({ path: path.join(output, `${name}-old.png`) });
        const after = await next.screenshot({ path: path.join(output, `${name}-new.png`) });
        assert.deepEqual(after, before, `Visual layout changed: ${name}`);
        const bounds = await next.getByLabel('家长咨询输入', { exact: true }).boundingBox();
        assert.ok(bounds.y >= 0 && bounds.y + bounds.height <= viewport.height);
        comparisons.push({ viewport, route, identical: true });
      }
      await clean.close();
    }
  }
  const report = { passed: true, copiedFiles: manifest.files.length, modelCalls: calls, apiRequests: requests, errors, comparisons };
  await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally {
  await browser.close(); await new Promise(resolve => server.close(resolve));
}
