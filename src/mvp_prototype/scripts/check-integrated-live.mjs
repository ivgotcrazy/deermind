// Explicit one-turn provider check. Offline browser tests never call a paid model.
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
if (!process.argv.includes('--run')) {
  console.log('Use --run to send one synthetic question through the integrated UI and configured provider.');
  process.exit(0);
}
const base = 'http://127.0.0.1:5178';
const output = fileURLToPath(new URL('../../../.tmp/v2-rebase-live-check/', import.meta.url));
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
let sessionId;
try {
  const status = await (await page.request.get(`${base}/api/live/status`)).json();
  if (!status.configured) throw Error('Live model is not configured.');
  await page.goto(`${base}/structure.html?role=student#/textbook`);
  await page.getByLabel('向 DeerMind 提问', { exact: true }).fill('这是一条原型连通性检查：甲有12张卡片，乙有9张，甲比乙多几分之几？请简短解释比较标准，暂时不要出题。');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await page.waitForURL(/#\/textbook\?chat=/);
  sessionId = new URL(page.url().split('#')[1], 'http://local').searchParams.get('chat');
  const deadline = Date.now() + 120000;
  let session;
  while (Date.now() < deadline) {
    session = await (await page.request.get(`${base}/api/live/sessions/${sessionId}`)).json();
    if (session.error) throw Error(session.error.message);
    if (!session.pending && session.turns?.some(turn => turn.role === 'assistant')) break;
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  if (!session?.turns?.some(turn => turn.role === 'assistant')) throw Error('Live response timed out.');
  await page.locator('.message-row:not(.user)').first().waitFor({ timeout: 10000 });
  await page.getByLabel('页面上下文：教材').waitFor();
  await page.getByLabel('向真实 DeerMind 提问').fill('保留的连通性检查草稿');
  await page.reload();
  await page.getByLabel('向真实 DeerMind 提问').waitFor();
  if (await page.getByLabel('向真实 DeerMind 提问').inputValue() !== '保留的连通性检查草稿') throw Error('Draft recovery failed.');
  await page.screenshot({ path: `${output}/student.png`, animations: 'disabled' });
  await page.goto(`${base}/structure.html?role=admin#/actual`);
  await page.getByRole('button', { name: '选择会话' }).click();
  await page.getByLabel('实际会话查阅用途').fill('检查整合后真实输入和回复是否可追溯');
  await page.getByRole('button', { name: '按用途打开实际会话' }).click();
  await page.getByText('正式评价：尚未执行。临时模型反馈不等于正式学习状态。', { exact: true }).waitFor();
  await page.screenshot({ path: `${output}/admin.png`, animations: 'disabled' });
  if (errors.length) throw Error(errors.join('\n'));
  const summary = { result:'PASS', checkedAt:new Date().toISOString(), sessionId, model:status.model, userTurns:session.turns.filter(t=>t.role==='user').length, assistantTurns:session.turns.filter(t=>t.role==='assistant').length, ms:session.turns.at(-1)?.metrics?.ms, errors };
  await writeFile(`${output}/result.json`, JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary));
} catch (error) {
  console.error(error.message);
  await page.screenshot({ path: `${output}/failure.png` });
  process.exitCode = 1;
} finally {
  await browser.close();
}
