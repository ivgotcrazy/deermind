import { chromium, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createPreviewServer } from './serve.mjs';

const out = fileURLToPath(new URL('../../design/assets/activities-v0.1/', import.meta.url));
await mkdir(out, { recursive: true });
const server = createPreviewServer();
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 }, locale: 'zh-CN' });
  const base = 'http://127.0.0.1:' + server.address().port;
  const b = name => page.getByRole('button', { name, exact: true });
  const screens = [];
  async function shot(id, subject, locator, clip) {
    await expect(locator).toBeVisible();
    await locator.scrollIntoViewIfNeeded();
    await page.evaluate(() => document.fonts.ready);
    const png = await page.screenshot({ path: out + id + '.png', animations: 'disabled', ...(clip ? { clip } : {}) });
    screens.push({ id, subject, viewport: page.viewportSize(), crop: clip, route: new URL(page.url()).pathname + new URL(page.url()).hash, sha256: createHash('sha256').update(png).digest('hex') });
  }
  await page.goto(base + '/admin/#/interaction');
  await shot('IA01', '讲解蓝图与节点定义', b('讲解蓝图'));
  await b('编辑节点').click();
  await shot('IA02', '节点内容、允许动作和无法继续时的处理', page.getByRole('dialog'));
  const own = page.getByRole('dialog').locator('fieldset');
  const first = await own.first().boundingBox(), last = await own.last().boundingBox();
  await shot('IA03', '节点仅选择本节点规则和推荐策略', own.first(), { x: first.x, y: first.y, width: first.width, height: last.y + last.height - first.y });
  await b('取消').click();
  await b('编辑条件转移').click();
  await page.setViewportSize({ width: 1600, height: 2200 });
  await shot('IA04', '节点内配置有序条件转移', page.getByRole('dialog'));
  await b('取消').click();await page.setViewportSize({ width: 1600, height: 1400 });
  await b('活动规则').click();
  await shot('IA05', '活动规则与规则定义', page.getByLabel('活动级规则配置'));
  await b('选择活动规则').click();
  await shot('IA06', '选择对所有节点生效的活动规则', page.getByRole('dialog'));
  await b('取消').click();await b('新增规则').click();
  await shot('IA07', '新增规则定义，保存后另选引用位置', page.getByRole('dialog'));
  await b('取消').click();await b('活动推荐策略').click();
  await shot('IA08', '活动推荐策略与可搜索的策略定义', page.getByLabel('活动级策略配置'));
  await b('选择活动推荐策略').click();
  await shot('IA09', '选择活动推荐策略', page.getByRole('dialog'));
  await b('取消').click();await b('对比辨析').first().click();
  await shot('IA10', '策略目的、适用条件及具体组织', page.getByRole('heading', { name: '对比辨析', exact: true }));
  for (const [kind, name, node, id] of [
    ['question', '答疑', '节点 2：回应问题', 'IA11'],
    ['assessment', '检测', '节点 2：检测轮', 'IA12'],
    ['free', '自由交谈', '节点 2：转交学习活动', 'IA13'],
  ]) {
    await page.goto(base + '/admin/#/interaction?kind=' + kind);
    await expect(b(name + '蓝图')).toBeVisible();await b(node).click();
    await shot(id, name + '蓝图及专属节点', b(name + '蓝图'));
  }
  await page.goto(base + '/admin/#/interaction?kind=assessment');
  await page.getByRole('button', { name: /连接：轮后处理 → 准备检测/ }).click();
  await shot('IA14', '帮助后重新准备检测，不恢复旧轮', page.getByLabel('节点条件转移'));
  await page.goto(base + '/student/');
  await page.getByLabel('教材', { exact: true }).selectOption('BNU-6A');
  await page.getByLabel('学习目标').selectOption({ index: 1 });await b('创建并进入教材').click();
  await b('讲讲增加四分之一').click();
  await shot('IS01', '学生单页：教材、持续对话与讲解', page.getByRole('log'));
  await b('先问一个相关问题').click();await b('回到原来的主线').click();
  await page.getByRole('textbox').fill('我想检测');await b('发送').click();await b('开始检测').click();
  await page.getByLabel('我的答案（本）').fill('150');await b('提交作答').click();await b('下一轮').click();
  await page.getByLabel('我的答案（升）').fill('48 ÷ 4');await b('结束检测并求助').click();
  await expect(page.getByRole('log')).not.toContainText('48 ÷ 4 = 12');
  await shot('IS02', '先结束检测轮，保留草稿，尚未给提示', b('讲讲刚才这道题'));
  await b('讲讲刚才这道题').click();
  await shot('IS03', '检测轮后的讲解子活动，随后可返回主线', b('回到原来的主线'));
  await page.goto(base + '/admin/#/interaction?kind=trace');
  await shot('IR01', '当前浏览器的活动树与运行追溯', page.getByRole('navigation', { name: '活动树' }));
  const configurations = {};
  for (const kind of ['explanation', 'question', 'assessment', 'free']) {
    await page.goto(base + '/admin/#/interaction?kind=' + kind + '&tab=rules');
    await b('选择活动规则').click();await b('保存活动配置').click();
    // Save the unchanged defaults in this isolated context to export the exact UI definitions.
    configurations[kind] = await page.evaluate(kind => {
      const key = kind === 'explanation' ? 'deermind-m1-teaching-v1' : 'm1-activity-model-' + kind + '-v1';
      const { blueprint, rules, strategies, activityRules, activityStrategies } = JSON.parse(localStorage.getItem(key));
      return { blueprint, rules, strategies, activityRules, activityStrategies };
    }, kind);
  }
  await writeFile(out + 'activity-configurations.json', JSON.stringify({ purpose: '本批截图采用的初始 mock 定义；不是生产协议或运行结果', configurations }, null, 2) + '\n');
  await writeFile(out + 'capture-manifest.json', JSON.stringify({ capturedAt: new Date().toISOString(), viewport: [1600, 1400], data: '独立浏览器固定 mock；不调用 LLM，不改变用户草稿', screens }, null, 2) + '\n');
} finally {
  await browser.close();await new Promise(resolve => server.close(resolve));
}
