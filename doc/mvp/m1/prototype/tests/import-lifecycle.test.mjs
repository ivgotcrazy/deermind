import test from 'node:test';
import assert from 'node:assert/strict';
import { chromium,expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';
const expect=baseExpect.configure({timeout:10000});
// The old source/semantic tabs were replaced. Keep upload, interruption and deletion coverage here.
test('import lifecycle keeps domain requirement, source pages and scoped draft deletion',async t=>{
  const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'msedge'});const page=await browser.newPage();page.setDefaultTimeout(10000);page.on('dialog',d=>d.accept());
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});const btn=name=>page.getByRole('button',{name,exact:true});
  await page.goto('http://127.0.0.1:'+server.address().port+'/admin/#/textbooks');await btn('导入教材').click();await expect(btn('上传并开始整理')).toBeDisabled();await btn('新建领域').click();await page.getByLabel('领域名称',{exact:true}).fill('导入边界测试领域');await btn('创建并选用').click();
  await page.locator('input[type=file]').setInputFiles({name:'notes.txt',mimeType:'text/plain',buffer:Buffer.from('text')});await expect(page.getByRole('alert')).toContainText('请选择PDF');
  await page.locator('input[type=file]').setInputFiles({name:'scan.png',mimeType:'image/png',buffer:Buffer.from([1,2,3])});await btn('上传并开始整理').click();await expect(page.getByRole('alert')).toContainText('未接入OCR');
  await btn('载入真实教材书页').click();await expect(page.locator('.upload-files tbody tr')).toHaveCount(5);await page.getByText('Mock处理场景',{exact:true}).click();await page.getByLabel('模拟一次识别中断').check();await btn('上传并开始整理').click();await expect(page.getByRole('alert')).toContainText('模拟识别中断');await btn('继续整理').click();await expect(page.locator('.material-contents')).toBeVisible();
  await page.locator('.element-title').first().click();await btn('查看原页').click();await page.locator('.original-preview img').evaluate(img=>img.decode());await btn('取消').click();
  await expect(btn('原页核对')).toHaveCount(0);await expect(btn('检查并应用')).toHaveCount(0);await expect(btn('解析内容')).toBeVisible();
  const before=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-import-v1'))[0]);await page.reload();assert.equal((await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-import-v1'))[0])).id,before.id);
  // Old import bookmarks enter the new chapter workspace, without modifying legacy source records.
  await page.evaluate(()=>{const ds=JSON.parse(localStorage.getItem('deermind-m1-import-v1'));delete ds[0].flow;localStorage.setItem('deermind-m1-import-v1',JSON.stringify(ds));location.hash='/textbooks?tab=import&source='+ds[0].id;});await page.reload();await expect(page.locator('.material-contents')).toBeVisible();
  const adapted=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-import-v1'))[0]);assert.deepEqual(adapted.integration,before.integration);assert.deepEqual(adapted.contentReview,before.contentReview);assert.ok(adapted.flow.elements.length);
  await btn('← 返回教材列表').click();await btn('导入教材').click();await btn('← 返回教材列表').click();const rows=page.locator('.data-table tbody tr');await expect(rows).toHaveCount(2);const empty=rows.filter({hasText:'未命名教材'});await empty.getByRole('button',{name:'删除导入 未命名教材',exact:true}).click();await btn('确认删除').click();await expect(rows).toHaveCount(1);const remaining=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-import-v1')));assert.equal(remaining[0].id,before.id);assert.ok(remaining[0].flow.elements.length);assert.ok((await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')))).domains.length);
});
