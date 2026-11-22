// E01-17 隔离浏览器用例。使用当前环境已安装的 Playwright 和 Chromium。
const assert = require('node:assert/strict');
const { writeFile } = require('node:fs/promises');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_WS_BROWSER_ORIGIN ?? 'http://127.0.0.1:5186';
const evidence = process.env.M1_TEST_WS_BROWSER_SCREENSHOT;
const secure = origin.startsWith('https:');

async function recordViewport(page) {
  if (!evidence) return async () => {};
  const cdp = await page.context().newCDPSession(page);
  const frames = [];
  cdp.on('Page.screencastFrame', ({ data, sessionId, metadata }) => {
    if (frames.length < 50) frames.push({ data, timestamp: metadata.timestamp });
    void cdp.send('Page.screencastFrameAck', { sessionId });
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', maxWidth: 900, maxHeight: 600 });
  return async () => {
    await cdp.send('Page.stopScreencast');
    await writeFile(evidence.replace(/\.png$/, '-frames.json'), JSON.stringify(frames));
    await cdp.detach();
  };
}

async function changeAccountAcrossTabs(page) {
  const first = await page.context().newPage();
  const second = await page.context().newPage();
  const oldConnections = [];
  first.on('websocket', (socket) => oldConnections.push(socket));
  await first.goto(origin + '/admin/');
  await first.getByText('合成学生', { exact: true }).waitFor();
  await second.goto(origin + '/admin/');
  await second.getByText('合成学生', { exact: true }).waitFor();
  const active = oldConnections.filter((socket) => !socket.isClosed());
  assert.equal(active.length, 1);
  const closed = active[0].waitForEvent('close');
  await second.getByRole('button', { name: '退出登录' }).click();
  await first.getByRole('button', { name: '登录' }).waitFor();
  await closed;
  await second.getByLabel('账号').fill('operator');
  await second.getByLabel('密码').fill('synthetic-test-password-only');
  await second.getByRole('button', { name: '登录' }).click();
  await first.getByText('合成管理员', { exact: true }).waitFor();
  assert.equal(await first.getByText('合成学生', { exact: true }).count(), 0);
  if (evidence) await first.screenshot({ path: evidence.replace(/\.png$/, '-tabs.png') });
  console.log('两标签页验证通过：退出后旧连接关闭，换账号后两页都显示当前身份。');
}

async function run() {
  const browser = await chromium.launch({
    executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE,
  });
  try {
    const context = await browser.newContext({ ignoreHTTPSErrors: secure });
    const page = await context.newPage();
    const messages = [];
    const reads = [];
    const errors = [];
    let connections = 0;
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('websocket', (socket) => {
      const url = new URL(socket.url());
      assert.equal(url.pathname, '/ws');
      assert.equal(url.protocol, secure ? 'wss:' : 'ws:');
      connections++;
      socket.on('framesent', ({ payload }) => {
        const { type, request_id: requestId } = JSON.parse(payload.toString());
        if (type === 'command') messages.push(requestId);
      });
    });
    page.on('response', (response) => {
      if (new URL(response.url()).pathname === '/api/m1/requests/receipt') reads.push(response);
    });

    await page.goto(origin + '/student/');
    await page.getByLabel('账号').fill('student');
    await page.getByLabel('密码').fill('synthetic-test-password-only');
    await page.getByRole('button', { name: '登录' }).click();
    await page.getByText('待确认', { exact: true }).waitFor();
    const cookie = (await page.context().cookies(origin)).find(
      (item) => item.name === (secure ? '__Host-dm_session' : 'dm_session_local'),
    );
    assert.ok(cookie);
    assert.equal(cookie.secure, secure);
    assert.equal(cookie.httpOnly, true);
    const response = page.waitForResponse(
      (result) => result.url().includes('/requests/receipt') && result.ok(),
    );
    const stopRecording = await recordViewport(page);
    await page.getByRole('button', { name: '确认使用' }).click();
    const observed = await (await response).json();
    await page.getByText('completed', { exact: true }).waitFor();
    await page.getByText('已通过', { exact: true }).waitFor();
    await page.getByText('ready', { exact: true }).waitFor();
    await stopRecording();

    assert.equal(connections, 2);
    assert.equal(messages.length, 1);
    assert.equal(observed.receipt_state, 'completed');
    assert.equal(new URL(reads[0].url()).searchParams.get('request_id'), messages[0]);
    assert.deepEqual(errors, []);
    if (evidence) await page.screenshot({ path: evidence });
    console.log(
      `Chromium ${browser.version()} ${origin}：重连后补读收据 ${messages[0]}，仅发送一次写入。`,
    );
    if (process.env.M1_TEST_WS_BROWSER_TABS === 'true') await changeAccountAcrossTabs(page);
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
