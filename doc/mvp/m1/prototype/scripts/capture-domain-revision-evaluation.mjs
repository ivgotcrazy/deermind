import { chromium } from '@playwright/test';
import { mkdir, writeFile, readFile, copyFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createPreviewServer } from './serve.mjs';

const out = fileURLToPath(new URL('../../design/assets/domain-model-v0.1/', import.meta.url));
await mkdir(out, { recursive: true });
const server = createPreviewServer();
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge'});
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN' });
  const go = path => page.goto('http://127.0.0.1:' + server.address().port + '/admin/#/' + path);
  const button = name => page.getByRole('button', { name, exact: true });
  const records = [];
  const capture = async (file, subject, anchor) => {
    await anchor.scrollIntoViewIfNeeded();
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: out + file + '.png', animations: 'disabled' });
    records.push({ file: file + '.png', subject, route: new URL(page.url()).hash });
  };
  await go('evaluation');
  await button('打开四分之一样例').click();
  const claim = page.getByRole('heading', { name: '比例增加任务的理解与求解' });
  await capture('E01', 'Task 与方法入口', claim);
  await button('编辑基本信息').click();
  await capture('E02', '名称与适用评价方面', page.getByRole('dialog'));
  await button('取消').click();
  const library = page.locator('.criterion-library');
  await library.locator('summary').first().click();
  await button('编辑判据 计算增加量并加回原量').click();
  await capture('E03', '本 Task 可复用执行判据的字段', page.getByRole('dialog'));
  await button('取消').click();
  await library.locator('summary').first().click();
  await button('先求增加量，再加原量 · 关联执行判据').click();
  await capture('E04', '为分步法选择本方法判据', page.getByRole('dialog'));
  await button('取消').click();
  await page.getByRole('tab', { name: '按原量的 1+r 倍计算' }).click();
  await button('编辑理解与解释规则').click();
  await capture('E06', '倍数法的理解与解释规则', page.getByRole('dialog'));
  await button('取消').click();
  await go('targets?id=TARGET-M1-QUARTER-SEPARATE');
  const req = page.getByRole('button', { name: /^编辑要求 / }).first();
  await capture('G01', '目标、教材与四分之一要求', page.getByRole('heading', { name: '教材范围' }));
  await req.click();
  await capture('G02', '要求的章节、Claim 与任务范围', page.getByLabel('学习要求名称', { exact: true }));
  await page.getByLabel('要求的方法覆盖').selectOption('all');
  await page.getByRole('checkbox', { name: /已核对：范围在 Task 内/ }).check();
  await button('保存学习要求').click();
  await capture('G03', '同一要求改为两法分别达标', page.locator('.method-standards tbody').last());
  await go('targets');
  await button('新建学习目标').click();
  const book = page.getByLabel('教材', { exact: true });
  await book.selectOption({ index: 1 });
  await capture('G04', '新建目标选择教材与章节', page.getByRole('dialog'));
  await button('取消').click();
  await go('evaluation');
  await button('新建 Claim').click();
  await capture('E07', '在教材以外从领域和任务创建 Claim', page.getByRole('dialog'));
  await button('取消').click();
  await button('打开四分之一样例').click();
  await button('编辑基本信息').click();
  await page.getByLabel('Claim 名称').fill('比例增加任务的理解与求解（第二版）');
  await button('保存修改').click();
  await go('targets?id=TARGET-M1-QUARTER-SEPARATE');
  await capture('G05', 'Claim 修订后学习要求提示核对', page.locator('.requirement-card .callout').first());
  await writeFile(out + 'evaluation-capture.json', JSON.stringify({ viewport: [1440, 1000], data: '独立浏览器；四分之一 mock 样例', screens: records }, null, 2) + '\n');
  const previous=JSON.parse(await readFile(out+'capture-manifest.json','utf8'));
  const screens=previous.shots?previous.shots.map(s=>({file:s.name+'.png',route:s.route,source:'solution-template.test.mjs'})):previous.screens.filter(s=>s.file.startsWith('D'));
  screens.push(...records.map(s=>({...s,source:'capture-domain-revision-evaluation.mjs'})));
  const material={
    'T10-intake-actions':'material-flow/07-row-actions',
    'T11-extract-definition':'material-flow/08-extract-template',
    'T12-partial-intake':'material-flow/09-partial-completion',
    'T13-intake-complete':'material-flow/04-intake-complete',
    'T14-add-chapter-link':'material-flow/10-add-chapter-link',
    'T15-edit-chapter-link':'material-flow/11-edit-chapter-link',
    'T16-chapter-links':'material-flow/03-chapter-links',
    'T17-add-knowledge':'intake-dialog/process',
  };
  for(const [name,source] of Object.entries(material)){
    await copyFile(new URL('../test-results/'+source+'.png',import.meta.url),out+name+'.png');
    screens.push({file:name+'.png',source:'test-results/'+source+'.png'});
  }
  for(const s of screens)s.sha256=createHash('sha256').update(await readFile(out+s.file)).digest('hex');
  await writeFile(out+'capture-manifest.json',JSON.stringify({capturedAt:new Date().toISOString(),type:'Independent browser mock; no LLM',screens},null,2));
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
