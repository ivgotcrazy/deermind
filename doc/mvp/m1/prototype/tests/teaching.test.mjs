import test from 'node:test';
import assert from 'node:assert/strict';
import { chromium, expect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

test('M1 教学模型与四分之一走查', async t => {
  const server = createPreviewServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch();
  t.after(async () => { await browser.close(); await new Promise(resolve => server.close(resolve)); });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  page.setDefaultTimeout(6000);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const button = name => page.getByRole('button', { name, exact: true });
  await page.goto('http://127.0.0.1:' + server.address().port + '/admin/');
  await button('交互活动').click();

  await t.test('蓝图直达检测，并可查看和保存推荐策略', async () => {
    await expect(page.getByRole('heading', { name: '交互活动管理' })).toBeVisible();
    await page.getByRole('button', { name: /连接：讲解与互动 → 检测与反馈/ }).click();
    await expect(page.getByLabel('蓝图定义详情')).toContainText('学生同意独立检测');
    await button('活动推荐策略').click();
    await button('对比辨析').click();
    await button('停用策略').click();
    await page.reload();
    await expect(button('启用策略')).toBeVisible();
    await button('活动规则').click();
    await page.getByText('适用的系统约束 · 只读').click();
    await expect(page.locator('.system-boundaries')).toContainText('实质求助先结束检测');
  });
  await t.test('三个旧情境各能推进，改后保留固定示例的版本提示', async () => {
    await page.goto(page.url().split('#')[0]+'#/interaction?tab=scenes');
    for (const name of ['基础含义不清楚', '会算但解释不清', '已理解，检验迁移']) {
      await button(name).click();
      await button('下一轮').click();
      await expect(button('上一轮')).toBeEnabled();
    }
    await expect(page.getByText(/示例待核对/)).toBeVisible();
    await button('← 返回教学蓝图').click();
  });
  await t.test('没有推荐仍可讲解，直接检测后先结束再展示提示', async () => {
    await page.goto(page.url().split('#')[0]+'#/interaction?tab=quarter');
    await expect(page.getByRole('status')).toContainText('没有命中推荐');
    await page.getByText(/本节点推荐的策略/).click();
    await expect(page.locator('.quarter-events + details')).not.toContainText('对比辨析');
    await button('继续讲解').click();
    await expect(page.getByLabel('走查记录')).toContainText('80×(1＋1/4)');
    await button('同意并开始独立检测').click();
    await expect(button('展示检测后提示')).toHaveCount(0);
    await expect(page.getByLabel('走查记录')).not.toContainText('150 本');
    await page.getByLabel('独立作答').fill('我先找原量');
    await button('请求提示').click();
    await expect(page.getByLabel('走查记录')).toContainText('未提交草稿');
    await expect(page.getByLabel('走查记录')).toContainText('因求助结束');
    await expect(page.getByLabel('走查记录')).not.toContainText('检测后提示');
    await expect(button('提交作答')).toHaveCount(0);
    await button('展示检测后提示').click();
    await expect(page.getByLabel('走查记录').locator('li').last()).toContainText('检测后提示');
  });
  await t.test('正常提交、退出与重新走查', async () => {
    await button('重新走查').click(); await button('继续讲解').click();
    await button('同意并开始独立检测').click();
    await expect(button('提交作答')).toBeDisabled();
    await page.getByLabel('独立作答').fill('150 本，原量是 120 本。');
    await button('提交作答').click();
    await expect(page.getByLabel('走查记录')).toContainText('已提交并结束');
    await button('重新走查').click(); await button('结束本次学习').click();
    await expect(button('继续讲解')).toHaveCount(0);
    assert.deepEqual(errors, []);
  });
  await t.test('移除直接检测的连接，新走查不能绕过已保存蓝图', async () => {
    await button('讲解蓝图').click();
    await page.getByRole('button', { name: /连接：讲解与互动 → 检测与反馈/ }).click();
    await button('编辑条件转移').click();
    const rows=page.locator('.routing-edit-row');
    let index=-1;
    for(let i=0;i<await rows.count();i++)if(await rows.nth(i).getByLabel('转移名称').inputValue()==='讲解后直接检测')index=i;
    assert.ok(index>=0);
    const row=rows.nth(index);
    await row.getByRole('button',{name:'删除',exact:true}).click();
    await button('应用到草稿').click(); await button('保存蓝图').click();
    await page.reload();
    await page.goto(page.url().split('#')[0]+'#/interaction?tab=quarter'); await button('继续讲解').click();
    await expect(button('同意并开始独立检测')).toBeDisabled();
    await expect(page.getByRole('status')).toContainText('没有从讲解直接进入检测');
  });
});
