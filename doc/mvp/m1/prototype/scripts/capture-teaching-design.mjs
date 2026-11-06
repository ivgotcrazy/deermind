import { chromium, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createPreviewServer } from './serve.mjs';

const out = fileURLToPath(new URL('../../design/assets/teaching-v0.1/', import.meta.url));
await mkdir(out, { recursive: true });
const server = createPreviewServer();
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, locale: 'zh-CN' });
  const button = name => page.getByRole('button', { name, exact: true });
  const screens = [];
  async function shot(id, subject, locator) {
    await locator.scrollIntoViewIfNeeded();
    await page.evaluate(() => document.fonts.ready);
    const png = await page.screenshot({ path: out + id + '.png', animations: 'disabled' });
    screens.push({ id, subject, route: new URL(page.url()).hash, sha256: createHash('sha256').update(png).digest('hex') });
  }
  await page.goto('http://127.0.0.1:' + server.address().port + '/admin/#/interaction');
  const direct = page.getByRole('button', { name: /连接：讲解与互动 → 检测与反馈/ });
  await direct.click();
  await shot('B01', '讲解后直接检测的条件', page.getByLabel('蓝图定义详情'));
  await button('编辑连接').click();
  await shot('B02', '编辑转移的起点、终点、条件与依据', page.getByRole('dialog'));
  await button('取消').click();
  await button('教学策略').click();
  await shot('B03', '策略筛选、新建及推荐阶段', page.getByLabel('教学策略筛选'));
  await button('对比辨析').click();
  await shot('B04', '策略的适用条件与教学组织', page.getByRole('heading', { name: '对比辨析', exact: true }));
  await button('教学规则').click();
  await page.getByText('适用的系统约束 · 只读').click();
  await shot('B05', '教学规则和系统只读边界', page.locator('.system-boundaries'));
  await button('情境推演').click();
  for (const [id, name] of [['S01','基础含义不清楚'],['S02','会算但解释不清'],['S03','已理解，检验迁移']]) {
    await button(name).click(); await button('下一轮').click();
    await shot(id, name, page.locator('.conversation h3'));
  }
  await button('← 返回教学蓝图').click(); await button('四分之一走查').click();
  const log = page.getByLabel('走查记录');
  await page.getByText(/本阶段推荐的策略/).click();
  await shot('Q01', '无推荐命中，讲解仍可开始', button('继续讲解'));
  await button('继续讲解').click();
  await shot('Q02', '从已有加法解释倍数', button('同意并开始独立检测'));
  await button('同意并开始独立检测').click();
  await page.getByLabel('独立作答').fill('我先找原量 120 本');
  await shot('Q03', '独立检测与未提交作答', button('请求提示'));
  await button('请求提示').click();
  await expect(log).toContainText('因求助结束');
  await expect(log).not.toContainText('检测后提示');
  await shot('Q04', '检测已结束，草稿保留，尚未展示提示', button('展示检测后提示'));
  await button('展示检测后提示').click();
  await shot('Q05', '提示属于检测后讲解', log.locator('li').last());
  await button('教学蓝图').click(); await direct.click(); await button('编辑连接').click();
  await button('移除连接').click(); await button('确认移除').click(); await button('保存蓝图').click();
  await button('四分之一走查').click(); await button('继续讲解').click();
  await expect(button('同意并开始独立检测')).toBeDisabled();
  await shot('Q06', '移除直接检测连接后的新走查', button('同意并开始独立检测'));
  await writeFile(out + 'capture-manifest.json', JSON.stringify({ viewport: [1440,1100], data: '独立浏览器，固定 mock', screens }, null, 2) + '\n');
} finally {
  await browser.close(); await new Promise(resolve => server.close(resolve));
}
