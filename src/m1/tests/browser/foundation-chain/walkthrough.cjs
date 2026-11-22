// Isolated E01-18 browser test with the fixture API and the same-origin HTTPS proxy.
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { writeFile } = require('node:fs/promises');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_E0118_BROWSER_ORIGIN ?? 'https://127.0.0.1:5196';
const expectedDigest = hash('foundation-chain'.repeat(12000));
const receiptPath = '/api/m1/requests/receipt';
const resultPath = '/api/m1/test/foundation-chain/results/';
const action = 'test.foundation_chain';
const deadline = 120_000;

function hash(value) {
  return createHash('sha256').update(value).digest('hex');
}

function observe(page) {
  const sockets = [];
  const watches = new Set();
  const commands = [];
  const errors = [];
  const receipts = [];
  const httpReads = [];
  const resultReads = new Map();
  page.on('websocket', (socket) => {
    const number = sockets.push(socket);
    const url = new URL(socket.url());
    assert.equal(url.origin.replace(/^wss:/, 'https:'), origin);
    assert.equal(url.pathname, '/ws');
    socket.on('framesent', ({ payload }) => {
      const frame = JSON.parse(payload.toString());
      if (frame.type === 'command') {
        commands.push({
          number,
          frameId: frame.frame_id,
          requestId: frame.request_id,
          action: frame.action,
          body: hash(JSON.stringify(frame.payload)),
        });
      }
    });
    socket.on('framereceived', ({ payload }) => {
      const frame = JSON.parse(payload.toString());
      if (frame.type === 'watch_ready' && frame.views.includes('foundation_chain'))
        watches.add(frame.watch_id);
      if (frame.type === 'receipt') {
        receipts.push({
          frameId: frame.frame_id,
          requestId: frame.request_id,
          receiptRef: frame.owner_receipt_ref,
          executionRef: frame.execution_ref,
        });
      }
      if (frame.type === 'error') {
        errors.push({
          requestId: frame.request_id,
          code: frame.error.code,
          acceptance: frame.acceptance,
        });
      }
    });
  });
  page.on('response', (response) => {
    const url = new URL(response.url());
    if (url.pathname === receiptPath && response.ok())
      httpReads.push(url.searchParams.get('request_id'));
    if (url.pathname.startsWith(resultPath) && response.ok())
      resultReads.set(url.pathname.slice(resultPath.length), response);
  });
  return { sockets, watches, commands, errors, receipts, httpReads, resultReads };
}

async function readReceipt(context, requestId) {
  const auth = await context.request.get(origin + '/api/m1/auth/session');
  assert.equal(auth.status(), 200);
  const session = await auth.json();
  const response = await context.request.get(origin + receiptPath, {
    params: {
      action,
      resource_kind: 'account',
      resource_id: session.account.account_id,
      request_id: requestId,
    },
    headers: { 'X-Expected-Session': session.session_id },
  });
  assert.equal(response.status(), 200);
  return response.json();
}

async function control(context, data) {
  const response = await context.request.post(origin + '/api/m1/test/foundation-chain/control', {
    data,
    headers: { Origin: origin },
  });
  assert.ok(response.ok(), `fixture control returned ${response.status()}`);
}

function scenario(page, name) {
  const row = page.locator(`[data-case="${name}"]`);
  return {
    id: () => row.getAttribute('data-request-id'),
    send: () => row.getByRole('button').click(),
    wait: (state) => row.getByText(state, { exact: true }).waitFor({ timeout: deadline }),
    waitForResult: () =>
      row.getByText(expectedDigest, { exact: true }).waitFor({ timeout: deadline }),
  };
}

function assertWrites(observed, requestId, count) {
  const matches = observed.commands.filter((item) => item.requestId === requestId);
  assert.equal(matches.length, count);
  for (const item of matches) {
    assert.equal(item.action, action);
    assert.equal(item.body, hash(JSON.stringify({ text: '四分之一合成输入' })));
  }
  return matches;
}

async function assertResult(receipt, observed) {
  assert.equal(receipt.receipt_state, 'completed');
  assert.equal(receipt.execution_state, 'completed');
  assert.ok(receipt.receipt_ref);
  assert.ok(receipt.execution_ref);
  assert.equal(receipt.result_refs[0].path, expectedDigest);
  const read = observed.resultReads.get(receipt.result_refs[0].id);
  assert.ok(read);
  const result = await read.json();
  assert.equal(result.execution_id, receipt.result_refs[0].id);
  assert.equal(result.sha256, expectedDigest);
  assert.match(result.input_event_id, /^[0-9a-f-]{36}$/);
  assert.match(result.source_event_id, /^[0-9a-f-]{36}$/);
  return { input_event_id: result.input_event_id, source_event_id: result.source_event_id };
}

async function run() {
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const context = await browser.newContext({ ignoreHTTPSErrors: true });
    const page = await context.newPage();
    const observed = observe(page);
    let pageErrors = 0;
    page.on('pageerror', () => pageErrors++);

    await page.goto(origin + '/student/');
    await page.getByLabel('账号').fill('student');
    await page.getByLabel('密码').fill('synthetic-test-password-only');
    await page.getByRole('button', { name: '登录' }).click();
    await page.locator('#watch').getByText('ready', { exact: true }).waitFor();
    const cookie = (await context.cookies(origin)).find(
      (item) => item.name === '__Host-dm_session',
    );
    assert.ok(cookie?.secure && cookie.httpOnly);
    await control(context, { busy: false, drop_next_receipt: false, restart_worker: false });

    // Repeating the same request after completion returns the saved result and identities.
    const normal = scenario(page, 'normal');
    const normalId = await normal.id();
    const notification = observed.sockets.at(-1).waitForEvent('framereceived', {
      predicate: ({ payload }) => {
        const frame = JSON.parse(payload.toString());
        if (frame.type !== 'changed' || !frame.views.includes('foundation_chain')) return false;
        assert.ok(observed.watches.has(frame.watch_id));
        assert.deepEqual(Object.keys(frame).sort(), [
          'request_id',
          'resource',
          'type',
          'views',
          'watch_id',
        ]);
        return true;
      },
      timeout: deadline,
    });
    await Promise.all([notification, normal.send()]);
    await normal.wait('completed');
    await normal.waitForResult();
    const first = await readReceipt(context, normalId);
    const normalEvents = await assertResult(first, observed);

    const duplicateReply = observed.sockets.at(-1).waitForEvent('framereceived', {
      predicate: ({ payload }) => {
        const frame = JSON.parse(payload.toString());
        return (
          frame.type === 'receipt' && frame.request_id === normalId && frame.state === 'completed'
        );
      },
      timeout: deadline,
    });
    await Promise.all([duplicateReply, normal.send()]);
    await normal.wait('completed');
    await normal.waitForResult();
    const [originalWrite, duplicateWrite] = assertWrites(observed, normalId, 2);
    assert.notEqual(duplicateWrite.frameId, originalWrite.frameId);
    assert.deepEqual(
      observed.receipts.find(({ frameId }) => frameId === duplicateWrite.frameId),
      {
        frameId: duplicateWrite.frameId,
        requestId: normalId,
        receiptRef: first.receipt_ref,
        executionRef: first.execution_ref,
      },
    );
    const duplicate = await readReceipt(context, normalId);
    assert.deepEqual(await assertResult(duplicate, observed), normalEvents);
    assert.equal(duplicate.receipt_ref, first.receipt_ref);
    assert.equal(duplicate.execution_ref, first.execution_ref);

    // Drop the socket after the server has saved acceptance and before its reply reaches Chromium.
    const lost = scenario(page, 'lost');
    const lostId = await lost.id();
    await control(context, { drop_next_receipt: true });
    const active = observed.sockets.at(-1);
    const activeNumber = observed.sockets.length;
    await Promise.all([active.waitForEvent('close'), lost.send()]);
    await lost.wait('completed');
    await page.locator('#watch').getByText('ready', { exact: true }).waitFor();
    assert.ok(observed.sockets.length > activeNumber);
    const [write] = assertWrites(observed, lostId, 1);
    assert.equal(write.number, activeNumber);
    assert.equal(
      observed.receipts.some((entry) => entry.requestId === lostId),
      false,
    );
    assert.ok(observed.httpReads.includes(lostId));
    await lost.waitForResult();
    const recovered = await readReceipt(context, lostId);
    const lostEvents = await assertResult(recovered, observed);

    // Worker replacement is independent from the browser connection and submission.
    const worker = scenario(page, 'worker');
    const workerId = await worker.id();
    const workerConnectionCount = observed.sockets.length;
    await control(context, { restart_worker: true });
    await worker.send();
    await worker.wait('completed');
    await worker.waitForResult();
    assert.equal(observed.sockets.length, workerConnectionCount);
    assertWrites(observed, workerId, 1);
    assert.ok(observed.httpReads.includes(workerId));
    const resumed = await readReceipt(context, workerId);
    const workerEvents = await assertResult(resumed, observed);

    // A pre-admission refusal must leave no receipt until the user sends again.
    const busy = scenario(page, 'busy');
    const busyId = await busy.id();
    await control(context, { busy: true });
    await busy.send();
    await busy.wait('rejected');
    assert.deepEqual(
      observed.errors.find((entry) => entry.requestId === busyId),
      {
        requestId: busyId,
        code: 'resource_busy',
        acceptance: 'not_accepted',
      },
    );
    assert.equal((await readReceipt(context, busyId)).receipt_state, 'not_found');
    await control(context, { busy: false });
    assert.equal((await readReceipt(context, busyId)).receipt_state, 'not_found');
    assertWrites(observed, busyId, 1);

    await busy.send();
    await busy.wait('completed');
    assertWrites(observed, busyId, 2);
    await busy.waitForResult();
    const retried = await readReceipt(context, busyId);
    const busyEvents = await assertResult(retried, observed);
    assert.equal((await readReceipt(context, normalId)).receipt_ref, first.receipt_ref);
    assert.equal(pageErrors, 0);

    const evidence = {
      browser: `Chromium ${browser.version()}`,
      transport: 'WSS',
      result_sha256: expectedDigest,
      normal: {
        request_id: normalId,
        receipt_ref: first.receipt_ref,
        execution_ref: first.execution_ref,
        ...normalEvents,
        writes: 2,
        changed: true,
        duplicate_receipt_matches: true,
      },
      lost: {
        request_id: lostId,
        receipt_ref: recovered.receipt_ref,
        execution_ref: recovered.execution_ref,
        ...lostEvents,
        writes: 1,
        writes_after_reconnect: 0,
        http_recovered: true,
      },
      worker: {
        request_id: workerId,
        receipt_ref: resumed.receipt_ref,
        execution_ref: resumed.execution_ref,
        ...workerEvents,
        writes: 1,
      },
      busy: {
        request_id: busyId,
        receipt_ref: retried.receipt_ref,
        execution_ref: retried.execution_ref,
        ...busyEvents,
        writes: 2,
        prior_receipt: 'not_found',
      },
    };
    if (process.env.M1_TEST_E0118_BROWSER_EVIDENCE) {
      await writeFile(
        process.env.M1_TEST_E0118_BROWSER_EVIDENCE,
        JSON.stringify(evidence, null, 2) + '\n',
      );
    }
    console.log(JSON.stringify(evidence));
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
