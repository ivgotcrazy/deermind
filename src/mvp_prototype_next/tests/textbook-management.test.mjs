import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { expect } from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/textbook-review-20261024/',import.meta.url));
await mkdir(output,{recursive:true});
test('textbooks preserve chapter context and map to current Domain definitions',async t=>{
  const server=createPrototypeServer({directory:output,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model call expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`;
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=(p,name)=>p.getByRole('button',{name,exact:true});
  const tab=(p,name)=>p.getByRole('tab',{name,exact:true});
  const dialog=p=>p.getByRole('dialog');
  const chapter='textbooks?id=BOOK-MATH&chapter=CH-INCREASE&tab=';
  async function journey(name,run,hash=chapter+'content'){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'}),p=await ctx.newPage(),errors=[],calls=[];
      p.setDefaultTimeout(6000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
      try{await p.goto(base+'#/'+hash);await run(p);assert.deepEqual(errors,[]);assert.deepEqual(calls,[]);}
      catch(e){await p.screenshot({path:output+'/failure-'+name.slice(0,18).replace(/\W/g,'-')+'.png',fullPage:true});throw e;}
      finally{await ctx.close();}
    });
  }
  await journey('list, directory search and chapter context stay separate',async p=>{
    await expect(p.locator('.textbook-list tbody tr')).toHaveCount(1);
    await p.getByLabel('搜索教材').fill('不存在');await expect(p.locator('.textbook-list tbody tr')).toHaveCount(0);
    await p.getByLabel('搜索教材').fill('自编');await btn(p,'小学数学·教材管理示例').click();
    await expect(p.getByRole('complementary',{name:'教材目录'})).toBeVisible();
    await btn(p,'按比例增加后的数量').click();await expect(p.locator('.chapter-header h3')).toHaveText('按比例增加后的数量');
    await p.getByLabel('查找章节').fill('三角形');await btn(p,'三角形的面积').click();await expect(p.locator('.source-sheet')).toContainText('底 AB 长 12 厘米');
    await p.getByLabel('查找章节').fill('');await tab(p,'领域映射').click();await expect(p.locator('.mapping-table tbody tr')).toHaveCount(1);await expect(p.locator('.mapping-table')).toContainText('底乘对应高，再除以二');
    await btn(p,'按比例增加后的数量').click();await expect(tab(p,'领域映射')).toHaveAttribute('aria-selected','true');await expect(p.locator('.mapping-table')).not.toContainText('底乘对应高');
    await btn(p,'← 返回教材列表').click();await expect(p.getByLabel('搜索教材')).toHaveValue('自编');
    await p.screenshot({path:output+'/verified-list.png',fullPage:true});
  },'textbooks');
  await journey('source links locate exact file page; source editing validates and cancels',async p=>{
    await btn(p,'书页 7 · 练习 3 ↗').click();await expect(tab(p,'章节内容')).toHaveAttribute('aria-selected','true');
    await expect(p.locator('.source-address')).toContainText('文件第 9 页 · 书页 7 · 练习 3');await expect(p.locator('.source-sheet')).toContainText('班级原有 40 本图书');
    await btn(p,'编辑来源定位').click();await dialog(p).getByLabel('页内位置').fill('未保存位置');await btn(p,'取消').click();await expect(p.locator('.source-address')).not.toContainText('未保存');
    await btn(p,'编辑来源定位').click();await dialog(p).getByLabel('文件页码').fill('0');await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toBeFocused();
    await dialog(p).getByLabel('文件页码').fill('11');await dialog(p).getByLabel('印刷书页码').fill('9');await dialog(p).getByLabel('页内位置').fill('练习 5');await btn(p,'保存').click();
    await expect(p.locator('.source-address')).toContainText('文件第 11 页 · 书页 9 · 练习 5');await tab(p,'领域映射').click();await expect(btn(p,'书页 9 · 练习 5 ↗')).toBeVisible();
    await btn(p,'书页 6 · 例 2 ↗').click();await expect(p.locator('.source-address')).toContainText('文件第 8 页');await p.screenshot({path:output+'/verified-content.png',fullPage:true});
  },chapter+'mapping');
  await journey('selected methods determine deduplicated recursive KC; links return to mapping',async p=>{
    await expect(p.locator('.knowledge-table tbody tr')).toHaveCount(2);await expect(p.locator('.knowledge-table')).not.toContainText('增加后的倍数');
    await btn(p,'编辑映射 fraction').click();await dialog(p).getByRole('checkbox',{name:/先求最终量对应的倍数/}).check();await btn(p,'取消').click();await expect(p.locator('.knowledge-table tbody tr')).toHaveCount(2);
    await btn(p,'编辑映射 fraction').click();await dialog(p).getByRole('checkbox',{name:/先求最终量对应的倍数/}).check();await btn(p,'保存映射').click();await expect(p.locator('.knowledge-table tbody tr')).toHaveCount(3);
    await p.locator('.mapping-table').getByRole('button',{name:'先求最终量对应的倍数 ↗',exact:true}).click();await expect(p.locator('.domain-detail h2')).toHaveText('先求最终量对应的倍数');await btn(p,'← 返回教材章节').click();await expect(tab(p,'领域映射')).toHaveAttribute('aria-selected','true');
    await p.locator('.knowledge-table tbody tr').first().getByRole('button').first().click();await expect(p.locator('.domain-detail')).toBeVisible();await btn(p,'← 返回教材章节').click();
    await btn(p,'已知原量和增加比例，求增加后的量 ↗').click();await btn(p,'编辑基本定义').click();await dialog(p).getByLabel('任务名称',{exact:true}).fill('修改后的领域任务名称');await btn(p,'保存基本定义').click();await btn(p,'← 返回教材章节').click();await expect(p.locator('.mapping-table')).toContainText('修改后的领域任务名称');
    await p.getByLabel('查找章节').fill('综合应用');await btn(p,'综合应用：扩建后的花园').click();await expect(p.locator('.knowledge-table tbody tr')).toHaveCount(6);
    await expect(p.locator('.mapping-table')).toContainText('整体面积减去花坛面积');await expect(p.locator('.knowledge-table')).not.toContainText('增加后的倍数');
    await p.getByLabel('查找章节').fill('');await p.screenshot({path:output+'/verified-recursive-mapping.png',fullPage:true});
  },chapter+'mapping');
  await journey('mapping additions require task, methods, source and rationale',async p=>{
    await btn(p,'添加任务映射').click();await btn(p,'保存映射').click();await expect(dialog(p).getByRole('alert')).toContainText('任务模板');
    await dialog(p).getByLabel('任务模板').selectOption('fraction');await btn(p,'保存映射').click();await expect(dialog(p).getByRole('alert')).toContainText('已有这个任务');
    await dialog(p).getByLabel('任务模板').selectOption('part');await btn(p,'保存映射').click();await expect(dialog(p).getByRole('alert')).toContainText('至少选择一种');
    await dialog(p).getByRole('checkbox',{name:/使用分数乘法/}).check();await btn(p,'保存映射').click();await expect(dialog(p).getByRole('alert')).toContainText('来源位置');
    await dialog(p).getByRole('checkbox',{name:/书页 6/}).check();await btn(p,'保存映射').click();await expect(dialog(p).getByRole('alert')).toContainText('为什么对应');
    await dialog(p).getByLabel('映射依据').fill('章节明确讲解了求增加量这一步，可作为部分量任务的教学材料。');await btn(p,'保存映射').click();await expect(p.locator('.mapping-table tbody tr')).toHaveCount(2);
    await expect(p.locator('.knowledge-table tbody tr')).toHaveCount(2);await expect(p.locator('.knowledge-table tbody tr').first()).toContainText('使用分数乘法求对应数量');
    await btn(p,'编辑映射 part').click();await btn(p,'移除此映射').click();await expect(btn(p,'确认移除')).toBeVisible();await btn(p,'确认移除').click();await expect(p.locator('.mapping-table tbody tr')).toHaveCount(1);
  },chapter+'mapping');
  await journey('directory editing, content review and related Claim navigation',async p=>{
    await btn(p,'新增单元').click();await dialog(p).getByLabel('单元名称').fill('补充单元');await btn(p,'保存').click();await btn(p,'在补充单元新增章节').click();await dialog(p).getByLabel('章节名称').fill('补充章节');await btn(p,'保存').click();
    await expect(p.locator('.chapter-header h3')).toHaveText('补充章节');await expect(p.locator('.prepared-panel')).toContainText('尚未整理');await tab(p,'领域映射').click();await expect(p.locator('.mapping-table tbody tr')).toHaveCount(0);
    await btn(p,'编辑章节').click();await dialog(p).getByLabel('所属单元').selectOption('UNIT-AREA');await dialog(p).getByLabel('章节名称').fill('调整后的章节');await btn(p,'保存').click();await expect(p.locator('.chapter-header')).toContainText('第二单元 图形面积');await expect(p.getByRole('button',{name:/^调整后的章节/})).toHaveAttribute('aria-current','page');
    await btn(p,'三角形的面积').click();await tab(p,'章节内容').click();await expect(p.locator('.review-row')).toContainText('内容已核对');await btn(p,'编辑整理内容').click();await dialog(p).getByLabel('整理内容',{exact:true}).fill('底和高应一一对应，面积为底乘高除以二。');await btn(p,'保存').click();await expect(p.locator('.review-row')).toContainText('待核对');
    await btn(p,'记录核对结果').click();await dialog(p).getByLabel('核对结果').selectOption('true');await dialog(p).getByLabel('核对依据与疑点').fill('已对照底高和单位，示例一致。');await btn(p,'保存').click();await expect(p.locator('.review-row')).toContainText('内容已核对');
    await tab(p,'准备情况').click();await btn(p,'三角形面积求解 ↗').click();await expect(p.locator('.claim-header h2')).toHaveText('三角形面积求解');await btn(p,'← 返回教材章节').click();await expect(tab(p,'准备情况')).toHaveAttribute('aria-selected','true');
    await btn(p,'前往目标管理 →').click();await expect(p.getByRole('heading',{name:'目标管理',exact:true})).toBeVisible();await btn(p,'← 返回教材章节').click();await expect(p.locator('.chapter-header h3')).toHaveText('三角形的面积');
  });
  await journey('import entry preserves a resumable draft in the existing textbook shell',async p=>{
    await btn(p,'导入教材').click();await expect(p.locator('.import-steps button')).toHaveCount(5);
    await p.getByText('使用其他演示数据',{exact:true}).click();await btn(p,'使用示例扫描件').click();await p.getByLabel('教材名称',{exact:true}).fill('试用教材');
    await btn(p,'← 返回教材列表').click();await expect(p.locator('.textbook-list tbody tr')).toHaveCount(1);
    await btn(p,'继续导入 试用教材').click();await p.reload();await expect(p.getByLabel('教材名称',{exact:true})).toHaveValue('试用教材');
    await expect(p.locator('.upload-files tbody tr')).toHaveCount(3);
  },'textbooks');
  await journey('observation remains read only and old work entry opens the current list',async p=>{
    await expect(p.locator('.observation-detail')).toContainText('MAT-001@1');await btn(p,'前往教材管理 →').click();await expect(p.locator('.textbook-list tbody tr')).toHaveCount(1);
    await btn(p,'← 返回观测来源').click();await expect(p.locator('.observation-detail')).toContainText('MAT-001@1');
    await btn(p,'运行总览').click();await p.getByRole('button',{name:/准备一个章节/}).click();await expect(p.locator('.textbook-list tbody tr')).toHaveCount(1);
  },'observed-object?id=MAT-001%401');
  await journey('deep links, keyboard tabs, narrow layout and real-mode boundary',async p=>{
    await expect(btn(p,'综合应用：扩建后的花园')).toHaveAttribute('aria-current','page');await expect(p.locator('.source-sheet')).toContainText('长方形花园');
    await tab(p,'章节内容').focus();await p.keyboard.press('ArrowRight');await expect(tab(p,'领域映射')).toBeFocused();
    await p.setViewportSize({width:1024,height:768});assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth>el.clientWidth),false);
    await p.screenshot({path:output+'/verified-narrow.png',fullPage:true});await btn(p,'编辑映射 composite').click();await expect(dialog(p)).toBeVisible();await p.screenshot({path:output+'/verified-mapping-editor.png',fullPage:true});await p.keyboard.press('Escape');await expect(dialog(p)).toHaveCount(0);
    await p.goto(base+'#/'+chapter+'content&source=missing');await expect(p.locator('.source-panel')).toContainText('这个来源位置不存在');
    await p.goto(base+'#/textbooks?id=BOOK-MATH&chapter=missing');await expect(p.getByRole('heading',{name:'章节不存在'})).toBeVisible();
    await p.getByLabel('数据来源',{exact:true}).selectOption('real');await expect(p.getByRole('heading',{name:'尚未接入真实模型数据'})).toBeVisible();await expect(btn(p,'导入教材')).toHaveCount(0);
  },'textbooks?id=BOOK-MATH&chapter=CH-GARDEN&tab=content');
});
