import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { expect } from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/target-review-20261024/',import.meta.url));
await mkdir(output,{recursive:true});
test('targets connect current textbook chapters and per-Claim learning requirements',async t=>{
  const server=createPrototypeServer({directory:output,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model call expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`,browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=(p,name)=>p.getByRole('button',{name,exact:true}),dialog=p=>p.getByRole('dialog');
  const target='targets?id=TARGET-MATH',fraction=target+'&claim=CLAIM-FRACTION';
  async function journey(name,run,hash=target){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'}),p=await ctx.newPage(),errors=[],calls=[];
      p.setDefaultTimeout(6000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
      try{await p.goto(base+'#/'+hash);await run(p);assert.deepEqual(errors,[]);assert.deepEqual(calls,[]);}
      catch(e){await p.screenshot({path:output+'/failure-'+name.slice(0,20).replace(/\W/g,'-')+'.png',fullPage:true});throw e;}
      finally{await ctx.close();}
    });
  }
  await journey('list and links preserve target, chapter and Claim context',async p=>{
    await expect(p.locator('.target-list tbody tr')).toHaveCount(1);await p.getByLabel('搜索目标').fill('不存在');await expect(p.locator('.target-list tbody tr')).toHaveCount(0);
    await p.getByLabel('搜索目标').fill('分数');await btn(p,'分数与面积·学习目标示例').click();await expect(p.locator('.target-claims tbody tr')).toHaveCount(2);await expect(p.locator('.target-context')).toContainText('8 项要求');
    await btn(p,'配置 三角形面积求解').click();await expect(p.locator('.requirement-table tbody tr')).toHaveCount(4);await btn(p,'查看 Claim 定义 ↗').click();await expect(p.locator('.claim-header h2')).toHaveText('三角形面积求解');await btn(p,'← 返回学习目标').click();
    await btn(p,'底乘对应高，再除以二 ↗').click();await expect(p.locator('.domain-detail h2')).toHaveText('底乘对应高，再除以二');await btn(p,'← 返回学习目标').click();await expect(p.locator('.requirement-table tbody tr')).toHaveCount(4);
    await btn(p,'三角形的面积 ↗').click();await expect(p.locator('.chapter-header h3')).toHaveText('三角形的面积');await btn(p,'← 返回学习目标').click();await expect(p.locator('.target-claim-panel h3').first()).toHaveText('三角形面积求解');
    await btn(p,'← 返回目标列表').click();await expect(p.getByLabel('搜索目标')).toHaveValue('分数');await p.screenshot({path:output+'/verified-list.png',fullPage:true});
  },'targets');
  await journey('requirement edits and aspect choices are local to one target Claim',async p=>{
    const name='能独立求出增加后的数量';await btn(p,'编辑要求 '+name).click();await dialog(p).getByLabel('学习要求名称').fill('取消的要求');await btn(p,'取消').click();await expect(p.locator('.requirement-table')).not.toContainText('取消的要求');
    await btn(p,'编辑要求 '+name).click();await dialog(p).getByLabel('学习要求名称').fill('独立求解并说明参照量');await dialog(p).getByRole('checkbox',{name:/理解与解释/}).check();await dialog(p).getByLabel('达标标准').fill('独立列式、计算正确，并自行说明原量与增加量的关系。');await btn(p,'保存').click();
    const row=p.locator('.requirement-table tbody tr').filter({hasText:'独立求解并说明参照量'});await expect(row).toContainText('独立完成、理解与解释');await expect(row).toContainText('自行说明原量');
    await btn(p,'编辑要求 能说明为什么要把增加量加回原量').click();await btn(p,'移除此要求').click();await btn(p,'确认移除要求').click();await expect(p.locator('.requirement-table tbody tr')).toHaveCount(3);await expect(p.locator('.omission-note')).toHaveCount(0);
    await btn(p,'编辑要求 间隔后仍能独立解决同类问题').click();await btn(p,'移除此要求').click();await btn(p,'确认移除要求').click();await expect(p.locator('.omission-note')).toContainText('延迟保持');
    await btn(p,'编辑裁剪依据').click();await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toBeFocused();await dialog(p).getByLabel('裁剪依据').fill('本示例目标限于当次学习阶段；延迟目标另行明确，不改变 Claim。');await btn(p,'保存').click();
    await btn(p,'查看 Claim 定义 ↗').click();await p.getByRole('tab',{name:'评价方面'}).click();await expect(p.locator('.aspect-table tbody tr').filter({hasText:'延迟保持'})).toContainText('适用');await btn(p,'← 返回学习目标').click();
    await btn(p,'← 返回本目标的 Claim 列表').click();await btn(p,'配置 三角形面积求解').click();await expect(p.locator('.requirement-table tbody tr')).toHaveCount(4);await expect(p.locator('.omission-note')).toHaveCount(0);
  },fraction);
  await journey('requirements need meaningful fields, valid chapter and Claim aspects',async p=>{
    await btn(p,'添加学习要求').click();await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toContainText('名称');
    await dialog(p).getByLabel('学习要求名称').fill('能说明数量关系');await dialog(p).getByLabel('达标标准').fill('用自己的话说明增加量与原量之间的关系。');await dialog(p).getByRole('checkbox',{name:'按比例增加后的数量',exact:true}).uncheck();await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toContainText('章节');
    await dialog(p).getByRole('checkbox',{name:'按比例增加后的数量',exact:true}).check();await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toContainText('Claim 方面');await dialog(p).getByRole('checkbox',{name:/理解与解释/}).check();await btn(p,'保存').click();await expect(p.locator('.requirement-table tbody tr')).toHaveCount(5);
    await btn(p,'编辑要求 能说明数量关系').click();await dialog(p).getByLabel('达标标准').fill('不应保存');await p.keyboard.press('Escape');await expect(p.locator('.requirement-table')).not.toContainText('不应保存');
    await p.reload();await expect(p.locator('.requirement-table tbody tr')).toHaveCount(4);
  },fraction);
  await journey('new goals do not invent Claim coverage for unmapped chapters',async p=>{
    await btn(p,'新建目标').click();await btn(p,'创建目标').click();await expect(dialog(p).getByRole('alert')).toContainText('名称');await dialog(p).getByLabel('目标名称').fill('章节范围示例');await btn(p,'创建目标').click();await expect(dialog(p).getByRole('alert')).toContainText('至少一个');
    await dialog(p).getByRole('checkbox',{name:'求一个量的几分之几',exact:true}).check();await dialog(p).getByRole('checkbox',{name:/比例关系/}).check();await btn(p,'创建目标').click();await expect(p.locator('.target-header h2')).toHaveText('章节范围示例');await expect(p.locator('.target-claims tbody tr')).toHaveCount(0);
    await p.locator('.scope-panel summary').click();await expect(p.locator('.coverage-table')).toContainText('尚无 Claim');await btn(p,'纳入 Claim').click();await expect(dialog(p)).toContainText('没有可新增的 Claim');await dialog(p).getByRole('button',{name:'关闭',exact:true}).first().click();
    await btn(p,'前往评估模型管理 →').click();await expect(p.locator('.claim-list tbody tr')).toHaveCount(3);await btn(p,'← 返回学习目标').click();await expect(p.locator('.target-header h2')).toHaveText('章节范围示例');
    await btn(p,'编辑目标信息').click();await dialog(p).getByLabel('目标名称').fill('范围示例（更新）');await btn(p,'保存').click();await expect(p.locator('.target-header h2')).toHaveText('范围示例（更新）');await p.reload();await expect(p.getByRole('heading',{name:'未找到这个目标'})).toBeVisible();
  },'targets');
  await journey('scope narrowing cannot silently delete requirements; Claim removal is explicit',async p=>{
    await btn(p,'编辑章节范围').click();await dialog(p).getByRole('checkbox',{name:'按比例增加后的数量',exact:true}).uncheck();await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toContainText('先调整要求');await btn(p,'取消').click();await expect(p.locator('.target-context')).toContainText('2 章');
    await btn(p,'移除 Claim 增加后的数量求解').click();await btn(p,'取消').click();await expect(p.locator('.target-claims tbody tr')).toHaveCount(2);await btn(p,'移除 Claim 增加后的数量求解').click();await btn(p,'确认移除 Claim').click();await expect(p.locator('.target-claims tbody tr')).toHaveCount(1);
    await btn(p,'编辑章节范围').click();await dialog(p).getByRole('checkbox',{name:'按比例增加后的数量',exact:true}).uncheck();await btn(p,'保存').click();await expect(p.locator('.target-context')).toContainText('1 章');await expect(p.locator('.target-context')).toContainText('4 项要求');
    await btn(p,'模型管理').click();await btn(p,'评估空间').click();await expect(p.locator('.claim-list tbody tr')).toHaveCount(3);await expect(btn(p,'增加后的数量求解')).toBeVisible();
  });
  await journey('adding a Claim starts empty and only uses selected chapter tasks',async p=>{
    await btn(p,'纳入 Claim').click();await expect(dialog(p).locator('tbody tr')).toHaveCount(0);await p.keyboard.press('Escape');await btn(p,'编辑章节范围').click();await dialog(p).getByRole('checkbox',{name:'综合应用：扩建后的花园',exact:true}).check();await btn(p,'保存').click();
    await expect(p.locator('.target-claims tbody tr')).toHaveCount(2);await btn(p,'纳入 Claim').click();await expect(dialog(p).locator('tbody tr')).toHaveCount(1);await btn(p,'纳入 扩建后剩余面积求解').click();await expect(p.locator('.requirement-table tbody tr')).toHaveCount(0);await expect(p.locator('.omission-note')).toContainText('独立完成、理解与解释、迁移、延迟保持');
    await btn(p,'添加学习要求').click();await dialog(p).getByLabel('学习要求名称').fill('能组织综合任务的完整求解过程');await dialog(p).getByLabel('达标标准').fill('独立组织尺寸、面积与相减关系，结果及单位正确。');await dialog(p).getByRole('checkbox',{name:/独立完成/}).check();await btn(p,'保存').click();await expect(p.locator('.requirement-table tbody tr')).toHaveCount(1);
    await btn(p,'← 返回本目标的 Claim 列表').click();await expect(p.locator('.target-context')).toContainText('9 项要求');
  });
  await journey('any method accepts one mapped route; all methods requires each mapped route',async p=>{
    await expect(p.locator('.condition-issues')).toHaveCount(0);await expect(p.locator('.method-policy')).toContainText('任选一种');await expect(p.locator('.method-links button')).toHaveCount(2);
    await btn(p,'查看 Claim 定义 ↗').click();await btn(p,'编辑方法与支持边界').click();await dialog(p).getByLabel('方法覆盖要求').selectOption('all');await btn(p,'保存').click();await btn(p,'← 返回学习目标').click();await expect(p.locator('.condition-issues')).toContainText('未映射');
    await btn(p,'按比例增加后的数量 ↗').click();await btn(p,'编辑映射 fraction').click();await dialog(p).getByRole('checkbox',{name:/先求最终量对应的倍数/}).check();await btn(p,'保存映射').click();await btn(p,'← 返回学习目标').click();await expect(p.locator('.condition-issues')).toHaveCount(0);await expect(p.locator('.method-policy')).toContainText('分别覆盖全部');
    await btn(p,'查看 Claim 定义 ↗').click();await btn(p,'编辑方法与支持边界').click();await dialog(p).getByLabel('方法覆盖要求').selectOption('all');await btn(p,'保存').click();await btn(p,'← 返回学习目标').click();await expect(p.locator('.method-policy')).toContainText('分别覆盖全部');
    await p.screenshot({path:output+'/verified-requirements.png',fullPage:true});
  },fraction);
  await journey('textbook context filters goals; old observations remain historical; narrow layout',async p=>{
    await btn(p,'前往目标管理 →').click();await expect(p.locator('.context-filter')).toContainText('三角形的面积');await expect(p.getByLabel('筛选教材')).toHaveValue('BOOK-MATH');await btn(p,'← 返回教材章节').click();await expect(p.locator('.chapter-header h3')).toHaveText('三角形的面积');
    await p.goto(base+'#/observed-object?id=TG-001%401');await btn(p,'前往目标管理 →').click();await expect(p.locator('.target-list tbody tr')).toHaveCount(1);await btn(p,'← 返回观测来源').click();await expect(p.locator('.observation-detail')).toContainText('TG-001@1');
    await p.goto(base+'#/'+target);await p.setViewportSize({width:1024,height:768});assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth>el.clientWidth),false);await p.screenshot({path:output+'/verified-narrow.png',fullPage:true});
    await btn(p,'配置 三角形面积求解').click();await btn(p,'编辑要求 能独立选择底和高并计算面积').click();await expect(dialog(p)).toBeVisible();await p.screenshot({path:output+'/verified-editor.png',fullPage:true});await p.keyboard.press('Escape');
    await p.getByLabel('数据来源',{exact:true}).selectOption('real');await expect(p.getByRole('heading',{name:'尚未接入真实模型数据'})).toBeVisible();await expect(btn(p,'新建目标')).toHaveCount(0);
  },'textbooks?id=BOOK-MATH&chapter=CH-TRIANGLE&tab=readiness');
});
