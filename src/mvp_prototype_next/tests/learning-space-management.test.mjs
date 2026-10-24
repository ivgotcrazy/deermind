import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { expect } from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/learning-space-review-20261024/',import.meta.url));
await mkdir(output,{recursive:true});
test('learning spaces connect adopted curriculum, requirements and isolated personal examples',async t=>{
  const server=createPrototypeServer({directory:output,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model calls expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`,browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=(p,name)=>p.getByRole('button',{name,exact:true}),tab=(p,name)=>p.getByRole('tab',{name,exact:true}),dialog=p=>p.getByRole('dialog');
  const main='learning-spaces?id=SPACE-001';
  async function journey(name,run,hash=main){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'}),p=await ctx.newPage(),errors=[],calls=[];
      p.setDefaultTimeout(6000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
      try{await p.goto(base+'#/'+hash);await run(p);assert.deepEqual(errors,[]);assert.deepEqual(calls,[]);}
      catch(e){await p.screenshot({path:output+'/failure-'+name.slice(0,20).replace(/\W/g,'-')+'.png',fullPage:true});throw e;}
      finally{await ctx.close();}
    });
  }
  await journey('student search, filters, empty results and return context',async p=>{
    await expect(p.locator('.space-list tbody tr')).toHaveCount(3);await p.getByLabel('搜索学习空间').fill('学生 A');await expect(p.locator('.space-list tbody tr')).toHaveCount(2);
    await p.getByLabel('筛选学习记录').selectOption('empty');await expect(p.locator('.space-list tbody tr')).toHaveCount(1);await btn(p,'查看 学生 A的校外数学').click();await expect(p.locator('.space-header')).toContainText('SPACE-002');
    await btn(p,'← 返回空间列表').click();await expect(p.getByLabel('搜索学习空间')).toHaveValue('学生 A');await expect(p.getByLabel('筛选学习记录')).toHaveValue('empty');
    await p.getByLabel('搜索学习空间').fill('不存在');await expect(p.locator('.space-list tbody tr')).toHaveCount(0);await expect(p.locator('.empty')).toContainText('调整搜索');
    await p.getByLabel('搜索学习空间').fill('');await p.getByLabel('筛选学习记录').selectOption('');await p.getByLabel('筛选教材').selectOption('BOOK-MATH');await p.getByLabel('筛选学习目标').selectOption('TARGET-MATH');await expect(p.locator('.space-list tbody tr')).toHaveCount(3);
    await p.screenshot({path:output+'/verified-list.png',fullPage:true});await btn(p,'查看 学生 A的校内数学').click();await expect(p.locator('.personal-summary')).toContainText('共 8 项');await expect(p.locator('.result-counts')).toContainText('已达标');await p.screenshot({path:output+'/verified-overview.png',fullPage:true});
  },'learning-spaces');
  await journey('chapter task and direct method scope yields recursive deduplicated knowledge',async p=>{
    await tab(p,'课程范围').click();await btn(p,'综合应用：扩建后的花园').click();await expect(p.locator('.course-mappings tbody tr')).toHaveCount(1);
    await expect(p.locator('.course-mappings')).toContainText('整体面积减去花坛面积');await expect(p.locator('.course-mappings')).not.toContainText('先求增加量');await expect(p.locator('.course-knowledge tbody tr')).toHaveCount(6);await expect(p.locator('.course-knowledge')).not.toContainText('增加后的倍数');
    await p.screenshot({path:output+'/verified-course.png',fullPage:true});await p.locator('.course-mappings tbody td:nth-child(2) button').click();await expect(p.locator('.domain-detail h2')).toContainText('整体面积减去花坛面积');await btn(p,'← 返回学习空间').click();await expect(p.locator('.course-content h3').first()).toHaveText('综合应用：扩建后的花园');
    await btn(p,'查看教材当前映射 ↗').click();await expect(p.locator('.chapter-header h3')).toHaveText('综合应用：扩建后的花园');await btn(p,'← 返回学习空间').click();
    await btn(p,'比例关系').click();await expect(p.locator('.course-content')).toContainText('尚无 Task／Solution 映射');await expect(p.locator('.course-knowledge tbody tr')).toHaveCount(0);
    await p.getByLabel('查找章节').fill('不存在');await expect(p.locator('.chapter-button')).toHaveCount(0);await p.getByLabel('查找章节').fill('三角形');await expect(p.locator('.chapter-button')).toHaveCount(1);
  });
  await journey('requirements separate standards, Belief, evidence and untested aspects',async p=>{
    await tab(p,'学习要求与状态').click();await expect(p.locator('.space-claims tbody tr')).toHaveCount(2);await btn(p,'三角形面积求解').click();await expect(p.locator('.space-requirements tbody tr')).toHaveCount(4);
    await btn(p,'查看要求 能解释为什么底乘高后还要除以二').click();await expect(dialog(p)).toContainText('达标标准');await expect(dialog(p)).toContainText('需加强');await expect(dialog(p)).toContainText('SPACE-EV-004');
    await btn(p,'查看原始记录 · 解释底高关系与面积公式 →').click();await expect(dialog(p)).toContainText('我只能记住公式');await expect(dialog(p)).toContainText('先独立解释');await btn(p,'← 返回学习要求').click();await expect(dialog(p)).toContainText('达标标准');await p.keyboard.press('Escape');
    await btn(p,'查看要求 间隔后仍能识别底高并求面积').click();await expect(dialog(p)).toContainText('待确认');await expect(dialog(p)).toContainText('暂无本空间的相应 Evidence');await expect(dialog(p)).not.toContainText('SPACE-EV-004');await p.keyboard.press('Escape');
    await p.locator('.belief-details summary').click();await expect(p.locator('.personal-beliefs tbody tr')).toHaveCount(4);await p.screenshot({path:output+'/verified-requirements.png',fullPage:true});
    await btn(p,'查看 Claim 当前定义 ↗').click();await expect(p.locator('.claim-header h2')).toHaveText('三角形面积求解');await btn(p,'← 返回学习空间').click();await p.locator('.claim-context summary').click();await btn(p,'查看目标当前要求 ↗').click();await expect(p.locator('.requirement-table tbody tr')).toHaveCount(4);await btn(p,'← 返回学习空间').click();await expect(p.locator('.space-requirements tbody tr')).toHaveCount(4);
  });
  await journey('any method accepts the adopted route; helped performance still remains pending',async p=>{
    await tab(p,'学习要求与状态').click();await btn(p,'增加后的数量求解').click();await expect(p.locator('.space-requirements')).toContainText('待确认');await expect(p.locator('.space-requirements')).not.toContainText('需加强');
    await expect(p.locator('.method-policy')).toContainText('可任选一种');await expect(p.locator('.space-requirements tbody tr')).toHaveCount(4);
    await btn(p,'查看要求 能独立求出增加后的数量').click();await expect(dialog(p)).toContainText('提示后完成');await expect(dialog(p)).toContainText('尚无足以支持');await p.keyboard.press('Escape');
    await tab(p,'学习记录').click();await p.getByLabel('筛选记录章节').selectOption('CH-INCREASE');await expect(p.locator('.space-records tbody tr')).toHaveCount(1);await btn(p,'查看记录 提示后求增加后的水量').click();await expect(dialog(p)).toContainText('实际帮助');await p.keyboard.press('Escape');
    await p.getByLabel('查找学习记录').fill('不存在');await expect(p.locator('.space-records tbody tr')).toHaveCount(0);
  });
  await journey('same learner and same Claim in another space never inherits evidence',async p=>{
    await expect(p.locator('.personal-summary')).toContainText('尚未形成此空间的个人判断');await expect(p.locator('.personal-summary')).toContainText('共 4 项');await expect(p.locator('.result-counts>div').first()).toContainText('0');
    await tab(p,'学习要求与状态').click();await expect(p.locator('.space-claims tbody tr')).toHaveCount(1);await btn(p,'三角形面积求解').click();await btn(p,'查看要求 能独立选择底和高并计算面积').click();await expect(dialog(p)).toContainText('暂无本空间的相应 Evidence');await expect(dialog(p)).not.toContainText('SPACE-EV');await p.keyboard.press('Escape');
    await tab(p,'学习记录').click();await expect(p.locator('.space-records tbody tr')).toHaveCount(0);await expect(p.locator('.empty')).toContainText('不借用其他空间');
    await p.goto(base+'#/learning-spaces?id=SPACE-003');await expect(p.locator('.personal-summary')).toContainText('尚未形成此空间的个人判断');await expect(p.locator('.result-counts>div').first()).toContainText('0');
  },'learning-spaces?id=SPACE-002');
  await journey('current edits do not rewrite adopted definitions or personal results',async p=>{
    await btn(p,'查看目标当前定义 ↗').click();await btn(p,'编辑目标信息').click();await dialog(p).getByLabel('目标名称').fill('新版目标名称');await btn(p,'保存').click();await btn(p,'← 返回学习空间').click();await expect(p.locator('.adoption-context')).not.toContainText('新版目标名称');await expect(p.locator('.adoption-warning')).toContainText('1 项');
    await btn(p,'采用版本与历史 1 项有变化').click();await expect(p.locator('.version-table tbody tr').filter({hasText:'学习目标'})).toContainText('v2');await btn(p,'查看采用快照 分数与面积·学习目标示例').click();await expect(dialog(p)).not.toContainText('新版目标名称');await expect(dialog(p)).toContainText('原采用内容');await p.keyboard.press('Escape');
    await tab(p,'学习要求与状态').click();await btn(p,'三角形面积求解').click();await btn(p,'查看 Claim 当前定义 ↗').click();await btn(p,'编辑方法与支持边界').click();await dialog(p).getByLabel('方法覆盖要求').selectOption('all');await btn(p,'保存').click();await btn(p,'← 返回学习空间').click();await expect(p.locator('.method-policy')).toContainText('可任选一种');await expect(p.locator('.adoption-warning')).toContainText('2 项');await expect(p.locator('.space-requirements')).toContainText('已达标');
    await p.screenshot({path:output+'/verified-version.png',fullPage:true});
  });
  await journey('narrow layouts, unknown routes, legacy trace links and real mode remain honest',async p=>{
    await p.setViewportSize({width:1024,height:768});await tab(p,'课程范围').click();await btn(p,'综合应用：扩建后的花园').click();assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth>el.clientWidth),false);await p.screenshot({path:output+'/verified-narrow.png',fullPage:true});
    await tab(p,'学习要求与状态').click();await btn(p,'三角形面积求解').click();assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth>el.clientWidth),false);
    await p.goto(base+'#/learning-spaces?id=UNKNOWN');await expect(p.getByRole('heading',{name:'未找到这个学习空间'})).toBeVisible();
    await p.goto(base+'#/learning-spaces?id=LS-001');await expect(p.locator('.page-desc')).toContainText('历史空间示例');await expect(btn(p,'查看本空间学习状态')).toBeVisible();
    await p.goto(base+'#/'+main);await p.getByLabel('数据来源',{exact:true}).selectOption('real');await expect(p.getByRole('heading',{name:'尚未接入真实模型数据'})).toBeVisible();await expect(p.locator('.learning-space-workspace')).toHaveCount(0);
  });
});
