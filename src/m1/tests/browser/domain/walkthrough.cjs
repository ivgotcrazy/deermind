// Exercise the E02-01 UI on the selected local test endpoint.
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN;
const evidenceDir = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const clusterLabel = process.env.M1_TEST_DOMAIN_CLUSTER_LABEL;
const createPath = '/api/m1/domain-definitions';
const listPath = '/api/m1/domains';
const receiptPath = '/api/m1/requests/receipt';
const sessionPath = '/api/m1/auth/session';
const first = clusterLabel ? `${clusterLabel} 数学` : '小学数学';
const second = clusterLabel ? `${clusterLabel} 科学` : '初中科学';
const attachmentNote = clusterLabel ? '附件验证'.repeat(3_000) : null;

function loginDetails() {
  if (origin === 'http://127.0.0.1:5184') {
    assert.ok(clusterLabel, 'Set M1_TEST_DOMAIN_CLUSTER_LABEL for the deployed test.');
  }
  if (clusterLabel) {
    assert.equal(origin, 'http://127.0.0.1:5184', 'Use the K3s review endpoint.');
    assert.match(clusterLabel, /^E02-01 验收 [a-z0-9-]+$/);
    for (const key of [
      'M1_TEST_DOMAIN_LOGIN',
      'M1_TEST_DOMAIN_PASSWORD',
      'M1_TEST_DOMAIN_STUDENT_LOGIN',
      'M1_TEST_DOMAIN_STUDENT_PASSWORD',
    ]) {
      assert.ok(process.env[key], `Missing ${key}`);
    }
  }
  const password = process.env.M1_TEST_DOMAIN_PASSWORD ?? 'synthetic-test-password-only';
  return {
    admin: [process.env.M1_TEST_DOMAIN_LOGIN ?? 'operator', password],
    student: [
      process.env.M1_TEST_DOMAIN_STUDENT_LOGIN ?? 'student',
      process.env.M1_TEST_DOMAIN_STUDENT_PASSWORD ?? password,
    ],
  };
}

async function signIn(page, [login, password]) {
  await page.getByLabel('账号').fill(login);
  await page.getByLabel('密码').fill(password);
  await page.getByRole('button', { name: '登录' }).click();
}

async function currentSession(page) {
  const response = await page.request.get(origin + sessionPath);
  assert.equal(response.status(), 200);
  return response.json();
}

function headers(session) {
  return {
    Origin: origin,
    'X-Expected-Session': session.session_id,
    'X-CSRF-Token': session.csrf_token,
  };
}

async function openCreate(page, name) {
  await page.getByRole('button', { name: '新建领域' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('领域名称').fill(name);
  await dialog.getByRole('button', { name: '保存领域' }).click();
}

async function readSelected(page, name) {
  const heading = page.getByRole('heading', { name, exact: true });
  await heading.waitFor();
  const detail = page.locator('.domain-detail');
  await detail.getByText('v1', { exact: true }).waitFor();
  const id = await detail.locator('dd').last().textContent();
  assert.match(id, /^[0-9a-f-]{36}$/);
  return id;
}

async function run() {
  assert.equal(new URL(origin).hostname, '127.0.0.1', 'Use a loopback test endpoint.');
  const accounts = loginDetails();
  if (evidenceDir) await mkdir(evidenceDir, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ ignoreHTTPSErrors: true });
    const requests = [];
    const receipts = [];
    const details = new Map();
    const websocket = { hello: false, ready: false };
    let committedResponse;
    let pageErrors = 0;
    page.on('pageerror', () => pageErrors++);
    page.on('websocket', (socket) => {
      if (new URL(socket.url()).pathname !== '/ws') return;
      socket.on('framesent', ({ payload }) => {
        if (JSON.parse(payload.toString()).type === 'hello') websocket.hello = true;
      });
      socket.on('framereceived', ({ payload }) => {
        if (JSON.parse(payload.toString()).type === 'ready') websocket.ready = true;
      });
    });
    page.on('response', (response) => {
      const url = new URL(response.url());
      if (url.pathname === receiptPath && response.ok()) {
        receipts.push({ requestId: url.searchParams.get('request_id'), response });
      }
      if (url.pathname.includes('/api/m1/domains/') && response.ok()) {
        details.set(url.pathname.split('/').at(-1), response);
      }
    });
    await page.route('**' + createPath, async (route) => {
      const body = route.request().postDataJSON();
      requests.push(body);
      if (requests.length === 1) {
        // The first attempt never reaches the service, so R04 should report no receipt.
        await route.abort('connectionreset');
      } else if (body.definition.name === second) {
        // The second domain is committed by the real API, then the browser loses the response.
        // The deployed case puts its long note on the PVC while keeping the UI name short.
        const response = await route.fetch({
          maxRetries: 0,
          ...(attachmentNote ? { postData: { ...body, change_note: attachmentNote } } : {}),
        });
        assert.equal(response.status(), 200);
        committedResponse = await response.json();
        await route.abort('connectionreset');
      } else await route.continue();
    });

    await page.goto(origin + '/admin/');
    const initialList = page.waitForResponse(
      (response) => new URL(response.url()).pathname === listPath && response.ok(),
    );
    await signIn(page, accounts.admin);
    const { items } = await (await initialList).json();
    if (clusterLabel) {
      assert.ok(items.every(({ name }) => name !== first && name !== second));
    } else {
      await page.getByText('还没有领域。', { exact: true }).waitFor();
    }
    const adminSession = await currentSession(page);
    assert.equal(adminSession.account.role, 'admin');

    await openCreate(page, first);
    await page.getByRole('button', { name: '用原请求重试' }).waitFor();
    assert.equal(requests.length, 1);
    assert.equal((await receipts[0].response.json()).receipt_state, 'not_found');
    await page.reload();
    await page.getByRole('button', { name: '用原请求重试' }).click();
    const firstId = await readSelected(page, first);
    assert.equal(requests.length, 2);
    assert.deepEqual(requests[0], requests[1]);
    await page.getByRole('button', { name: '返回领域列表' }).click();

    await openCreate(page, second);
    const secondId = await readSelected(page, second);
    assert.notEqual(secondId, firstId);
    assert.equal(requests.length, 3);
    const recovered = receipts.find(({ requestId }) => requestId === requests[2].request_id);
    assert.ok(recovered);
    const recoveredReceipt = await recovered.response.json();
    assert.equal(recoveredReceipt.receipt_state, 'completed');
    assert.equal(recoveredReceipt.receipt_ref, committedResponse.request_ref);
    assert.equal(recoveredReceipt.result.object_ref.object_id, secondId);
    if (evidenceDir) await page.screenshot({ path: path.join(evidenceDir, 'domain-detail.png') });

    await page.reload();
    const list = page.getByRole('table', { name: '领域列表' });
    await list.getByRole('button', { name: first }).waitFor();
    await list.getByRole('button', { name: second }).waitFor();
    const search = page.getByRole('searchbox', { name: '搜索领域' });
    if (clusterLabel) await search.fill(clusterLabel);
    assert.equal(await list.getByRole('button').count(), 2);
    if (evidenceDir) await page.screenshot({ path: path.join(evidenceDir, 'domain-list.png') });
    await search.fill(first);
    assert.equal(await list.getByRole('button').count(), 1);
    await list.getByRole('button', { name: first }).click();
    assert.equal(await readSelected(page, first), firstId);
    await page.getByRole('button', { name: '返回领域列表' }).click();
    await search.fill(second);
    assert.equal(await list.getByRole('button').count(), 1);
    await list.getByRole('button', { name: second }).click();
    assert.equal(await readSelected(page, second), secondId);
    assert.equal(requests.length, 3);
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
      false,
    );

    const output = {
      browser: `Chromium ${browser.version()}`,
      origin,
      explicit_retry_same_body: true,
      lost_response_recovered_without_resend: true,
      domains: [],
    };
    for (const [id, request] of [
      [firstId, requests[1]],
      [secondId, requests[2]],
    ]) {
      const { object } = await details.get(id).json();
      assert.match(object.source_event_id, /^[0-9a-f-]{36}$/);
      output.domains.push({
        id,
        version: 1,
        source_event_id: object.source_event_id,
        request_id: request.request_id,
        name: object.content.name,
      });
    }

    if (clusterLabel) {
      output.attachment_case = {
        source_event_id: output.domains[1].source_event_id,
        note_bytes: Buffer.byteLength(attachmentNote),
      };
      const crossed = await page.request.get(
        origin + `${listPath}/${firstId}/objects/${secondId}`,
        { headers: headers(adminSession) },
      );
      assert.equal(crossed.status(), 404);
      output.cross_domain_detail = 404;
      assert.deepEqual(websocket, { hello: true, ready: true });
      output.websocket = websocket;
    }

    await page.getByRole('button', { name: '管理员账号与退出登录', exact: true }).click();
    await page.getByRole('menuitem', { name: '退出登录', exact: true }).click();
    await signIn(page, accounts.student);
    await page.getByText('当前账号属于学生端。').waitFor();
    assert.equal(await page.getByRole('region', { name: '领域管理' }).count(), 0);
    assert.equal(pageErrors, 0);
    output.student_admin_actions_hidden = true;
    if (clusterLabel) {
      const studentSession = await currentSession(page);
      assert.equal(studentSession.account.role, 'student');
      const denied = await page.request.post(origin + createPath, {
        headers: headers(studentSession),
        data: { ...requests[2], request_id: randomUUID() },
      });
      assert.equal(denied.status(), 403);
      const foreign = await page.request.get(origin + receiptPath, {
        headers: headers(studentSession),
        params: {
          action: 'domain.save_definition',
          resource_kind: 'account',
          resource_id: adminSession.account.account_id,
          request_id: requests[2].request_id,
        },
      });
      assert.equal(foreign.status(), 404);
      output.student_write = denied.status();
      output.student_admin_receipt = foreign.status();
    }

    if (evidenceDir) {
      await writeFile(
        path.join(evidenceDir, 'browser.json'),
        JSON.stringify(output, null, 2) + '\n',
      );
    }
    console.log(JSON.stringify(output));
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
