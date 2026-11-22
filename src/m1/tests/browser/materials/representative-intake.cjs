// 在人工核对之后，使用同一部署完成一个代表性样例的采用、归类、入库和章节关联。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { isDeepStrictEqual } = require('node:util');
const { chromium } = require('playwright');

const cases = {
  C02: {
    title: '根据两级分数关系求部分量',
    task: '从原量和连续两级分数关系求最终部分量，记录运算和解释。',
    methods: [
      ['逐级求部分量', '先用原量乘第一层比例得到中间量，再用中间量乘第二层比例求最后的量。'],
      ['先合并两层比例', '先计算两个比例的乘积得到最终量占原量的比例，再乘原量。'],
    ],
  },
  C03: {
    title: '分数乘除辨错与说明',
    task: '核对分数乘除的题面和给定算式，指出演算错误并说明理由。',
    methods: [
      ['逐步核对算式变形', '逐步核对乘除变形和约分是否等价。'],
      ['用逆运算检查对应步骤', '先用逆运算检验再定位错误的步骤。'],
    ],
  },
  C05: {
    title: '从统计图读取和比较数据',
    task: '按图例和刻度从统计图读数，解释人口数据的数量、变化或构成。',
    methods: [['依据图例和单位读图', '先识别统计图类型、图例及单位，再读取或比较对应数据。']],
  },
  C06: {
    title: '比较圆与其他平面图形',
    task: '观察题面所给图形及标记，说明圆与其他图形在轮廓和其他特征上的不同。',
    methods: [['逐一比较图形特征', '观察所有给出的图形，比较轮廓是否有直边或顶点，以及各方向的形状差别。']],
  },
};
const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const id = process.env.M1_E02_REAL_MODEL;
const label = process.env.M1_TEST_RICH_DOMAIN_NAME;
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;

function paragraph(text) {
  return {
    schema_version: '1', role: 'definition', data_tables: [], source_refs: [],
    blocks: [{ block_id: 'text', type: 'paragraph', provenance: { source_refs: [], transformation: 'generated' },
      payload: { spans: [{ type: 'text', text }] } }],
  };
}

async function poll(read, pending, message) {
  for (const _ of Array(140)) {
    const current = await read();
    if (!pending(current)) return current;
    await new Promise((resolve) => setTimeout(resolve, 1800));
  }
  throw new Error(message);
}

function checkFidelity(task, references) {
  const blocks = task.body.content.blocks;
  if (id === 'C02') {
    assert.equal(references.length, 2);
    assert.ok(blocks.some((block) => block.payload.spans?.some((span) => span.type === 'response_blank')));
    assert.ok(task.body.teaching_aids?.some((aid) => JSON.stringify(aid.blocks).includes('你能看懂笑笑的方法吗')));
    const [left, right] = references.map((entry) => entry.body.content.blocks
      .find((block) => block.type === 'math_sequence').payload.lines);
    assert.deepEqual(left[1].expression.args[1].args[0].cancel_to, []);
    assert.deepEqual(left[1].expression.args[0].args[0].cancel_to, ['4', '1']);
    assert.equal(right[0].expression.args[1].op, 'group');
  }
  if (id === 'C06') {
    assert.equal(references.length, 0);
    assert.ok(blocks.some((block) => block.payload.spans?.some((span) => span.text?.includes('附页'))));
    const diagram = blocks.find((block) => block.type === 'diagram').payload;
    assert.deepEqual(diagram.objects.map((item) => item.shape).filter((shape) => shape !== 'point').sort(),
      ['circle', 'ellipse', 'hexagon', 'pentagon', 'square', 'triangle']);
    assert.equal(diagram.layout.points.length, 6);
    assert.equal(new Set(diagram.relations.map((relation) => relation.subject)).size, 6);
    assert.equal(new Set(diagram.relations.map((relation) => relation.object)).size, 6);
    const shapeBox = (shape) => diagram.layout.boxes.find((box) =>
      box.object_ref === diagram.objects.find((item) => item.shape === shape).object_id).box;
    assert.ok(shapeBox('ellipse')[2] > shapeBox('ellipse')[3]);
    assert.equal(shapeBox('square')[2], shapeBox('square')[3]);
  }
}

async function run() {
  const definition = cases[id];
  assert.ok(definition && label && evidence);
  assert.equal(process.env.M1_E02_REVIEWED_CASE, id);
  await mkdir(evidence, { recursive: true });
  const snapshot = JSON.parse(await readFile(path.join(evidence, id + '-candidate.json'), 'utf8'));
  assert.equal(snapshot.batch.coverage.complete, true);
  const task = snapshot.items.find((entry) => entry.kind === 'task_instance');
  const references = snapshot.items.filter((entry) => entry.kind === 'reference' && entry.parent_ref?.id === task?.candidate_id);
  assert.ok(task);
  if (id === 'C06') assert.deepEqual(snapshot.items.map((entry) => entry.kind), ['task_instance']);
  checkFidelity(task, references);
  const began = Date.now();
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 920 } });
    const api = page.request;
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const navigation = page.getByRole('navigation', { name: '管理功能' });
    await navigation.waitFor();
    const root = origin + '/api/m1';
    const session = await (await api.get(root + '/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };

    async function read(url) {
      const response = await api.get(url, { headers });
      assert.equal(response.status(), 200, await response.text());
      return response.json();
    }
    async function post(url, data, status = 200) {
      const response = await api.post(url, { headers, data });
      assert.equal(response.status(), status, await response.text());
      return response.json();
    }
    const books = await read(root + '/textbooks?name=' + encodeURIComponent(label));
    const book = books.items.find((entry) => entry.metadata.title === label);
    assert.ok(book);
    const domain = book.domain_id;
    const material = root + '/material-imports/' + book.import_id;
    const base = root + '/domains/' + domain;
    const candidate = material + '/candidate-batches/' + snapshot.batch.batch_id;
    const existing = await read(candidate);
    const adoption = existing.batch.decision_state === 'adopted' ? { already_adopted: true }
      : await post(candidate + '/decision', {
        request_id: randomUUID(), batch_ref: { batch_id: snapshot.batch.batch_id, batch_revision: snapshot.batch.batch_revision },
        expected_revision: existing.batch.decision_revision, decision: 'adopt',
      });
    function ref(entry) {
      return { candidate_id: entry.candidate_id, candidate_revision: entry.candidate_revision, basis_revision: entry.basis_revision };
    }
    const submission = await post(material + '/intake-submissions', {
      request_id: randomUUID(), adopted_content_refs: [ref(task)], parent_bindings: [],
    }, 202);
    const received = await poll(
      () => read(material + '/intake-submissions/' + submission.result.submission_id),
      (item) => item.status === 'submitted', '待入库提交超时',
    );
    assert.equal(received.status, 'received', JSON.stringify(received));
    const item = (await read(base + '/intake-items/' + received.items[0].id)).item;
    assert.equal(item.kind, 'task_instance');

    async function create(objectKind, content) {
      const query = new URLSearchParams({ kinds: objectKind, name: content.name });
      const candidates = await read(base + '/objects?' + query);
      const same = candidates.items.find((entry) => entry.name === content.name);
      if (same) return same.object_ref;
      const saved = await post(root + '/domain-definitions', {
        request_id: randomUUID(), object_kind: objectKind, action: 'create', domain_id: domain,
        definition: content, change_note: 'E02 代表性样例人工核对的定义',
      });
      return saved.result.object_ref;
    }
    const methods = [];
    for (const [name, text] of definition.methods)
      methods.push(await create('solution', { name, approach: paragraph(text), key_process: paragraph(text) }));
    const taskRef = await create('task', {
      name: definition.title, responsibility: paragraph(definition.task),
      expected_output: paragraph(definition.task), method_refs: methods,
    });
    async function check(intake, solution) {
      const key = randomUUID();
      await post(base + '/classification-checks', {
        request_id: key, intake_item_ref: intake.item_ref, task_ref: taskRef, solution_ref: solution,
      }, 202);
      const query = new URLSearchParams({ action: 'domain.classify_instance', resource_kind: 'domain', resource_id: domain, request_id: key });
      const receipt = await poll(() => read(root + '/requests/receipt?' + query),
        (entry) => entry.receipt_state === 'accepted', '归类检查超时');
      await writeFile(path.join(evidence, id + '-check-' + intake.item_ref.id + '.json'),
        JSON.stringify(receipt, null, 2));
      assert.equal(receipt.receipt_state, 'completed', JSON.stringify(receipt));
      const results = receipt.result.output.results;
      assert.ok(results.length && results.every((entry) => entry.result === 'matched'), JSON.stringify(receipt.result));
      return receipt.result;
    }
    const taskCheck = item.state === 'pending' ? await check(item) : null;
    const instance = taskCheck ? await post(base + '/intake-items/' + item.item_ref.id + '/actions', {
      request_id: randomUUID(), action: 'associate_task', expected_revision: item.item_ref.revision,
      task_ref: taskRef, classification_check_ref: taskCheck.check_ref,
    }) : await read(base + '/instances/' + item.result_ref.id + '?version=' + item.result_ref.version);
    const instanceId = instance.result?.object_ref.id ?? instance.instance_ref.object_id;
    const instancePath = base + '/instances/' + instanceId;
    const firstVersion = await read(instancePath + '?version=1');
    assert.deepEqual(firstVersion.content.statement, task.body.content);
    assert.deepEqual(firstVersion.content.reference_solutions, []);
    const storedReferences = [];
    if (id === 'C02') {
      const missing = await api.post(material + '/intake-submissions', { headers, data: {
        request_id: randomUUID(), adopted_content_refs: [ref(references[0])], parent_bindings: [],
      } });
      assert.equal(missing.status(), 400, await missing.text());
      const parent = await read(base + '/material-intake-parent?' + new URLSearchParams({
        import_id: book.import_id, candidate_id: task.candidate_id, revision: String(task.candidate_revision),
      }));
      const sent = await post(material + '/intake-submissions', {
        request_id: randomUUID(), adopted_content_refs: references.map(ref),
        parent_bindings: references.map((entry) => ({ candidate_ref: ref(entry), parent_item_ref: parent.item.item_ref })),
      }, 202);
      const accepted = await poll(
        () => read(material + '/intake-submissions/' + sent.result.submission_id),
        (entry) => entry.status === 'submitted', '参考解法未受理',
      );
      assert.equal(accepted.status, 'received', JSON.stringify(accepted));
      for (const entry of accepted.items) {
        const work = (await read(base + '/intake-items/' + entry.id)).item;
        if (work.state === 'completed') {
          storedReferences.push(work.result_ref);
          continue;
        }
        const method = /合并|合成|占气象|先求航模|几分之几/.test(work.title) ? methods[1] : methods[0];
        const checkResult = await check(work, method);
        const parentInstance = await read(base + '/intake-items/' + work.item_ref.id + '/parent');
        storedReferences.push(await post(base + '/intake-items/' + work.item_ref.id + '/actions', {
          request_id: randomUUID(), action: 'associate_solution', expected_revision: work.item_ref.revision,
          solution_ref: method, task_instance_ref: parentInstance.instance_ref,
          expected_version: parentInstance.instance_ref.version, classification_check_ref: checkResult.check_ref,
        }));
      }
    }
    const finalInstance = await read(instancePath);
    assert.deepEqual(finalInstance.content.statement, firstVersion.content.statement);
    assert.equal(finalInstance.content.reference_solutions.length, id === 'C02' ? 2 : 0);
    if (id === 'C02') {
      assert.equal(finalInstance.instance_ref.version, 3);
      assert.equal((await read(instancePath + '?version=2')).content.reference_solutions.length, 1);
      assert.deepEqual(finalInstance.content.reference_solutions.map((reference) => reference.solution_ref.object_id).sort(),
        methods.map((method) => method.object_id).sort());
      for (const reference of references) {
        assert.ok(finalInstance.content.reference_solutions.some((saved) =>
          isDeepStrictEqual(saved.content, reference.body.content)));
      }
    }
    const contents = await read(material + '/contents');
    const chapter = contents.chapters.find((entry) => entry.chapter_id === task.chapter_ref.id);
    assert.ok(chapter);
    const association = root + '/textbooks/' + book.textbook_id + '/chapters/' + chapter.chapter_id + '/associations';
    const priorAssociation = (await read(association)).items.find((entry) => entry.task_ref.object_id === taskRef.object_id);
    const linked = priorAssociation ?? await post(association, { request_id: randomUUID(), action: 'add', task_ref: taskRef, method_refs: methods });
    const associationView = (await read(association)).items.find((entry) => entry.task_ref.object_id === taskRef.object_id);
    assert.deepEqual(associationView.method_refs, methods);
    await writeFile(path.join(evidence, id + '-intake-chain.json'), JSON.stringify({
      adoption, received, taskCheck, instance, firstVersion, finalInstance, storedReferences, linked,
      duration_ms: Date.now() - began,
    }, null, 2));
    await navigation.getByRole('button', { name: '教材管理' }).click();
    await page.getByRole('searchbox', { name: '教材名称' }).fill(label);
    await page.getByRole('button', { name: '搜索' }).click();
    await page.getByRole('button', { name: label, exact: true }).click();
    await page.getByRole('button', { name: '章节关联', exact: true }).click();
    await page.getByRole('region', { name: '章节关联' }).getByRole('rowheader', { name: definition.title, exact: true }).waitFor();
    await page.screenshot({ path: path.join(evidence, id + '-chapter.png'), fullPage: true });
    console.log(id + ' 原页候选、采用、领域入库、章节关联可追溯');
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
