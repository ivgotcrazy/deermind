// 仅向已授权模型发送既有四例中的必要样图。
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.M1_TEST_DOMAIN_ORIGIN ?? 'http://127.0.0.1:5184';
const evidence = process.env.M1_TEST_DOMAIN_BROWSER_EVIDENCE;
const label = process.env.M1_TEST_RICH_DOMAIN_NAME;
const caseId = process.env.M1_E02_REAL_MODEL;
const correction = process.env.M1_E02_REPAIR === '1';
const alreadyUploaded = process.env.M1_E02_USE_UPLOADED === '1';
const clarify = process.env.M1_E02_CLARIFY === '1';
const fixture = path.resolve(__dirname, '../../../../mvp_foundation/m1/content-representation/round2');

const correctionPrompts = {
  C02: '合并跨页内容为一题。第一张图的条件和首问，加第二张图开头“请列式解决问题。”及答句空线，都是同一题。'
    + '两列原有解法都引用这道题，左边逐层法两行都保留，右边先合并比例。保留原印刷与约分笔迹，数字节点 '
    + 'cancel_to 支持约分改写：左列第二行 12 依次改写为 4、1，分母 3、4 分别改为 1；右列第二行 12 改为 3、分母 4 改为 1。'
    + '左列第二行 3/4 的分子 3 没有约分笔迹，cancel_to 必须为空。保留右列第一行括号。'
    + '答案仍为空线。底部“你能看懂笑笑的方法吗？”单列为教学辅助。人物插图保留出处即可，不把人数当数据。'
    + '核对范围只有两张图，按上批章节名提交一题、两解法。本题没有另列知识条目，避免另建KC，出处说明尽量简短。',
  C03: '原图第一行用二元 divide，左边是 multiply(7/8, 3/4)，右边是 1/3；不要添加 group 或显示括号。'
    + '原图第二行是等号后连续乘法 7/8 × 3/4 × 1/3，无括号。第二个分数分子 3 和最后分数分母 3 各带 '
    + 'cancel_to:["1"] 笔迹。第三行等号后 7/32。照录原题文字、不改错、不生成解答。沿用上一批章节名，'
    + '明确替换上一批同一道题。本轮范围只包括已上传图片的这道题。',
  C05: '保留三种图形和原题，区分柱状图和折线图，同组数据可以复用一个表。右侧饼图单列年龄段与百分比。'
    + '原题下方三个气泡都属教学辅助，在题目 teaching_aids 中单列，不能混入原题，也不建解法。'
    + '请放大核对饼图左侧灰色扇区标注是 5.20%，对应 60～64 岁。其他原标注 17.95%、63.35%、13.50% 照录。'
    + '印刷页码是右下角 93，与文件内页号 1 各自保存。只解析这一页，沿用章节名，压缩重复出处说明。',
  C06: '请解析全部已上传图片。电子稿只需一个题目、一段原文和一个 diagram，不另建知识或解法。'
    + 'diagram 的 objects 列出 circle、ellipse、triangle、square、pentagon、hexagon 和六个 point，各用唯一短编号。'
    + 'layout.view_box 可用 [0,0,832,175]，每个形状在 boxes 中给 [左,上,宽,高]，每个点在 points 中给 [x,y]。'
    + 'relations 的 inside 主语是点、目标是对应图形，basis=visual_observation，用本页 source_id。'
    + '从左到右的点约在 (159,102)、(282,102)、(410,113)、(520,102)、(630,105)、(749,102)，以原图为准。'
    + '输出 JSON 时 points 数组结束后依次闭合 layout、payload、diagram 块三个对象，再闭合 blocks 数组。'
    + '照录附页引用，不要求图片外附页。本页覆盖完整后只交付这一题，目录用“观察图形及位置关系”。',
};

const geometryCorrection = '修正上一批 C06。changes 只返回一项，action=add、kind=task_instance，'
  + 'local_key=t1、chapter_key=c1、parent_key=null、replaces=上一批题目的 candidate_id。'
  + 'catalog_changes 必须有一项，action=add、local_key=c1，name 照抄上一批章节名，'
  + '带 order、source_ids 和 reason。用这项定位原章节。retire 只列重复题干的知识记录的 candidate_id。'
  + '不用重新识别题干、六个点或对应关系，保留它们及原出处。校正 layout.boxes，按图从左到右，'
  + '圆约 [120,63,78,78]，横向椭圆约 [243,72,78,60]，三角形约 [367,65,84,74]，'
  + '正方形约 [485,67,70,70]，五边形约 [589,61,82,83]，六边形约 [706,64,87,76]。'
  + '以本页图像为准，保留原附页引用及简短出处。不另建知识、解法或教学提示。'
  + 'JSON 中依次关闭 layout、payload 和 diagram 块，再关闭 blocks 数组。';

async function run() {
  assert.ok(caseId in correctionPrompts && (caseId !== 'C03' || correction));
  assert.ok(evidence && label && process.env.M1_TEST_DOMAIN_LOGIN && process.env.M1_TEST_DOMAIN_PASSWORD);
  const cases = JSON.parse(await readFile(path.join(fixture, 'cases.json'), 'utf8'));
  const profile = cases.find((entry) => entry.id === caseId);
  const files = profile.regions.map((region) => path.join(fixture, region.file));
  await mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.M1_TEST_BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 920 } });
    await page.goto(origin + '/admin/');
    await page.getByLabel('账号').fill(process.env.M1_TEST_DOMAIN_LOGIN);
    await page.getByLabel('密码').fill(process.env.M1_TEST_DOMAIN_PASSWORD);
    await page.getByRole('button', { name: '登录' }).click();
    const navigation = page.getByRole('navigation', { name: '管理功能' });
    await navigation.waitFor();
    const session = await (await page.request.get(origin + '/api/m1/auth/session')).json();
    const headers = { Origin: origin, 'X-Expected-Session': session.session_id, 'X-CSRF-Token': session.csrf_token };
    if (correction || alreadyUploaded) {
      await navigation.getByRole('button', { name: '教材管理' }).click();
      await page.getByRole('searchbox', { name: '教材名称' }).fill(label);
      await page.getByRole('button', { name: '搜索' }).click();
      await page.getByRole('button', { name: label, exact: true }).click();
      if (correction) {
        await page.getByRole('button', { name: '核对候选', exact: true }).last().click();
        await page.getByRole('button', { name: '引用这批候选继续修正' }).click();
      }
    } else {
      const created = await page.request.post(origin + '/api/m1/domain-definitions', {
        data: { request_id: randomUUID(), action: 'create', object_kind: 'domain',
          definition: { name: label }, change_note: 'E02-18 代表性样例' }, headers,
      });
      assert.equal(created.status(), 200, await created.text());
      const domain = (await created.json()).result.object_ref;
      await navigation.getByRole('button', { name: '教材管理' }).click();
      await page.getByRole('button', { name: '上传教材' }).click();
      const dialog = page.getByRole('dialog');
      await dialog.getByLabel('所属领域').selectOption(domain.object_id);
      await dialog.getByLabel('教材名称').fill(label);
      await dialog.getByLabel('来源说明').fill(caseId + ' ' + profile.title);
      await dialog.getByLabel('教材文件').setInputFiles(files);
      await dialog.getByRole('button', { name: '上传并解析' }).click();
      await page.locator('summary').filter({ hasText: '教材原件' }).click();
      await page.locator('.assistant-chat li').filter({ has: page.getByText('教材助手', { exact: true }) }).first().waitFor({ timeout: 255_000 });
      await page.getByRole('button', { name: path.basename(files[0]) }).waitFor();
    }
    const assistant = page.getByRole('region', { name: '教材助手' });
    const started = page.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith('/messages'));
    const scopedPrompt = '请解析全部已上传图片，仅在这些图片限定范围内生成待核对候选。'
      + profile.scope
      + ' 图片范围外的内容无需列为本轮缺口。按图片中的章节标题组织；截图看不到章节标题时，本轮目录名使用'
      + '“' + profile.title + '”。保留真实出处，解题辅助提示若有，独立保存为教学辅助。';
    const prompt = correction && caseId === 'C06' ? geometryCorrection : correction || clarify
      ? correctionPrompts[caseId] : scopedPrompt;
    await assistant.getByLabel('给教材助手发消息').fill(prompt);
    await assistant.getByRole('button', { name: '发送' }).click();
    const response = await started;
    assert.equal(response.status(), 202, await response.text());
    const acceptance = await response.json();
    const endpoint = response.url();
    await writeFile(path.join(evidence, caseId + '-acceptance.json'), JSON.stringify(acceptance, null, 2), 'utf8');
    let reply;
    for (const _ of Array(145)) {
      const messages = await (await page.request.get(endpoint, { headers })).json();
      const turnMessages = messages.items.filter((item) => item.turn_ref === acceptance.request_ref);
      reply = turnMessages.find((item) => item.role === 'assistant');
      if (reply) {
        assert.deepEqual(turnMessages.map((item) => item.role).sort(), ['assistant', 'user']);
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    assert.ok(reply, 'assistant reply did not arrive');
    const ref = reply.explicit_refs.find((item) => item.type === 'candidate_batch');
    await writeFile(path.join(evidence, caseId + '-reply.json'), JSON.stringify(reply, null, 2), 'utf8');
    assert.ok(ref, JSON.stringify(reply.body));
    const batch = await (await page.request.get(endpoint.replace(/messages$/, 'candidate-batches/') + ref.id, { headers })).json();
    assert.ok(batch.items.every((item) => item.source_refs.length > 0));
    await writeFile(path.join(evidence, caseId + '-candidate.json'), JSON.stringify(batch, null, 2), 'utf8');
    await page.getByRole('region', { name: '待核对候选' }).waitFor();
    await page.screenshot({ path: path.join(evidence, caseId + '-candidate.png'), fullPage: true });
    console.log(caseId + ' ' + JSON.stringify({
      coverage: batch.batch.coverage,
      picks: batch.items.map((item) => [item.kind, item.body.title]),
    }));
  } finally {
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
