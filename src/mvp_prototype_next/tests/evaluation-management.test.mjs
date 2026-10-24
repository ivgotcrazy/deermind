import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '../../mvp_prototype/node_modules/playwright/index.mjs';
import { expect } from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/evaluation-review-20261024/',import.meta.url));
await mkdir(output,{recursive:true});
test('Claim management uses current Domain tasks and editable mock definitions',async t=>{
  const server=createPrototypeServer({directory:output,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model call expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`;
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=(p,name)=>p.getByRole('button',{name,exact:true});
  const tab=(p,name)=>p.getByRole('tab',{name,exact:true});
  const dialog=p=>p.getByRole('dialog');
  async function journey(name,run,hash='evaluation'){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'}),p=await ctx.newPage(),errors=[],calls=[];
      p.setDefaultTimeout(6000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
      try{await p.goto(base+'#/'+hash);await run(p);assert.deepEqual(errors,[]);assert.deepEqual(calls,[]);}
      finally{await ctx.close();}
    });
  }
  async function fraction(p){await btn(p,'增加后的数量求解').click();}

  await journey('list, task search, four aspects and direct Task/Solution return paths',async p=>{
    await expect(p.locator('.claim-list tbody tr')).toHaveCount(3);
    await expect(p.locator('input[type=file]')).toHaveCount(0);
    await p.getByLabel('搜索 Claim 或任务').fill('三角形的底');await expect(p.locator('tbody tr')).toHaveCount(1);
    await p.getByLabel('搜索 Claim 或任务').fill('');await fraction(p);
    await expect(p.getByRole('tablist',{name:'Claim 详情'}).getByRole('tab')).toHaveText(['基本定义','评价方面','证据解释','状态推断']);
    await btn(p,'已知原量和增加比例，求增加后的量 ↗').click();
    await expect(p.locator('.task-workspace h2')).toHaveText('已知原量和增加比例，求增加后的量');
    await btn(p,'编辑基本定义').click();await dialog(p).getByLabel('任务名称',{exact:true}).fill('更新后的领域任务');await btn(p,'保存基本定义').click();
    await btn(p,'← 返回 Claim').click();await expect(p.locator('.task-binding')).toContainText('更新后的领域任务');
    await btn(p,'先求增加量，再求总量 ↗').click();await expect(p.locator('.domain-detail h2')).toHaveText('先求增加量，再求总量');
    await btn(p,'← 返回 Claim').click();await expect(tab(p,'基本定义')).toHaveAttribute('aria-selected','true');
    await tab(p,'评价方面').click();await expect(p.locator('.aspect-table tbody tr')).toHaveCount(4);
  });
  await journey('basic and method edits save locally; cancel and Escape discard changes',async p=>{
    await fraction(p);await btn(p,'编辑基本定义').click();await dialog(p).getByLabel('Claim 名称').fill('取消内容');await btn(p,'取消').click();await expect(p.locator('.claim-header h2')).toHaveText('增加后的数量求解');
    await btn(p,'编辑基本定义').click();await dialog(p).getByLabel('Claim 名称').fill('退出内容');await p.keyboard.press('Escape');await expect(dialog(p)).toHaveCount(0);
    await btn(p,'编辑基本定义').click();await dialog(p).getByLabel('Claim 名称').fill('原量增加能力评价');await dialog(p).getByLabel('质量要求',{exact:true}).fill('说明参照量，计算及单位正确。');await btn(p,'保存').click();
    await expect(p.locator('.claim-header h2')).toHaveText('原量增加能力评价');await expect(p.getByRole('tabpanel')).toContainText('说明参照量，计算及单位正确。');
    await btn(p,'编辑方法与支持边界').click();await dialog(p).getByRole('checkbox',{name:'先求最终量对应的倍数'}).uncheck();await dialog(p).getByLabel('允许与不允许的帮助').fill('允许读题，不提供列式。');await btn(p,'保存').click();
    await expect(btn(p,'先求最终量对应的倍数 ↗')).toHaveCount(0);await expect(p.getByRole('tabpanel')).toContainText('允许读题，不提供列式。');
    await p.getByText('修改记录 · 3 条',{exact:true}).click();await expect(p.locator('.history')).toContainText('修改基本定义');
    await btn(p,'← 返回 Claim 列表').click();await expect(btn(p,'原量增加能力评价')).toBeVisible();await p.reload();await expect(btn(p,'增加后的数量求解')).toBeVisible();
  });
  await journey('aspect edits require trimming/extension reasons and retain inactive rules',async p=>{
    await fraction(p);await tab(p,'评价方面').click();await btn(p,'编辑延迟保持').click();await dialog(p).getByRole('checkbox').uncheck();await btn(p,'保存').click();
    await expect(dialog(p).getByRole('alert')).toContainText('请说明');await expect(dialog(p).getByRole('alert')).toBeFocused();
    await dialog(p).getByLabel('裁剪依据').fill('本次只定义即时表现，延迟保持在另一组明确条件下评价。');await btn(p,'保存').click();
    await expect(p.locator('.aspect-table tbody tr').filter({hasText:'延迟保持'})).toContainText('不适用');
    await tab(p,'证据解释').click();await p.getByRole('combobox',{name:'评价方面',exact:true}).selectOption('retention');await expect(p.locator('.rule-table')).toContainText('不参与解释');
    await tab(p,'评价方面').click();await btn(p,'编辑延迟保持').click();await dialog(p).getByRole('checkbox').check();await btn(p,'保存').click();
    await expect(p.locator('.aspect-table tbody tr').filter({hasText:'延迟保持'})).not.toContainText('裁剪依据');
    await btn(p,'添加评价方面').click();await dialog(p).getByLabel('方面名称').fill('合理性检查');await dialog(p).getByLabel('判断标准').fill('能检查最终量应大于原量。');await dialog(p).getByLabel('证据要求').fill('学生自己的比较理由。');await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toContainText('增加');
    await dialog(p).getByLabel('扩展依据').fill('区分计算完成与主动检查结果。');await btn(p,'保存').click();await expect(p.locator('.aspect-table tbody tr')).toHaveCount(5);
    await tab(p,'证据解释').click();await btn(p,'添加证据规则').click();await expect(dialog(p).getByRole('combobox',{name:'评价方面',exact:true}).locator('option')).toContainText(['请选择','独立完成','理解与解释','迁移','延迟保持','合理性检查']);
  });
  await journey('evidence rules support create, edit, cancel and confirmed deletion',async p=>{
    await fraction(p);await tab(p,'证据解释').click();await p.getByRole('combobox',{name:'评价方面',exact:true}).selectOption('independent');await expect(p.locator('.rule-table tbody tr')).toHaveCount(3);
    await expect(p.locator('.rule-table tbody tr').filter({hasText:'求助后的作答'})).toContainText('不具诊断性');
    await btn(p,'添加证据规则').click();await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toContainText('请填写');
    await dialog(p).getByLabel('观察类型').fill('识别结果待确认');await dialog(p).getByRole('combobox',{name:'证据意义',exact:true}).selectOption('neutral');await dialog(p).getByLabel('适用条件').fill('公式识别仍存在争议。');await dialog(p).getByLabel('证据解释').fill('等待确认原作答，不更新能力判断。');await btn(p,'保存').click();
    const row=p.locator('.rule-table tbody tr').filter({hasText:'识别结果待确认'});await expect(row).toContainText('不具诊断性');await row.getByRole('button').click();await dialog(p).getByLabel('证据解释').fill('不保存');await btn(p,'取消').click();await expect(row).toContainText('等待确认原作答');
    await row.getByRole('button').click();await dialog(p).getByLabel('证据解释').fill('先确认识别，再解释证据。');await btn(p,'保存').click();await expect(row).toContainText('先确认识别');
    await row.getByRole('button').click();await btn(p,'删除规则').click();await btn(p,'保留规则').click();await expect(btn(p,'确认删除')).toHaveCount(0);await btn(p,'删除规则').click();await btn(p,'确认删除').click();await expect(row).toHaveCount(0);
  });
  await journey('new Claim can use a newly created Domain task without inheriting evaluation',async p=>{
    await p.goto(base+'#/domain?domain=DOM-MATH&filter=task');await btn(p,'新建任务模板').click();await dialog(p).getByLabel('任务名称',{exact:true}).fill('领域中新建的任务');await btn(p,'创建任务模板').click();
    await btn(p,'评估模型管理').click();await btn(p,'新建 Claim').click();await btn(p,'创建 Claim').click();await expect(dialog(p).getByRole('alert')).toBeVisible();
    const taskOption=await dialog(p).getByLabel('关联 Task').locator('option').filter({hasText:'领域中新建的任务'}).getAttribute('value');await dialog(p).getByLabel('关联 Task').selectOption(taskOption);await btn(p,'创建 Claim').click();
    await expect(p.locator('.claim-header h2')).toHaveText('领域中新建的任务的能力评价');await tab(p,'评价方面').click();await expect(p.locator('.aspect-table tbody tr')).toHaveCount(4);await expect(p.locator('.aspect-table tbody tr').first()).toContainText('待补充');
    await tab(p,'证据解释').click();await expect(p.locator('.rule-table tbody tr')).toHaveCount(0);await tab(p,'状态推断').click();await expect(p.getByRole('tabpanel')).toContainText('待补充');
    await p.reload();await expect(p.getByRole('heading',{name:'未找到这个 Claim'})).toBeVisible();
  });
  await journey('inference changes stay in one Claim, keyboard tabs and narrow layout work',async p=>{
    await fraction(p);await tab(p,'状态推断').click();await btn(p,'编辑推断规则').click();await dialog(p).getByLabel('相互矛盾的证据').fill('先核对实际帮助，冲突未解释时保留不确定。');await btn(p,'保存').click();await expect(p.getByRole('tabpanel')).toContainText('先核对实际帮助');
    await btn(p,'← 返回 Claim 列表').click();await btn(p,'三角形面积求解').click();await tab(p,'状态推断').click();await expect(p.getByRole('tabpanel')).not.toContainText('先核对实际帮助');
    await tab(p,'基本定义').focus();await p.keyboard.press('ArrowRight');await expect(tab(p,'评价方面')).toBeFocused();await expect(tab(p,'评价方面')).toHaveAttribute('aria-selected','true');
    await p.setViewportSize({width:1024,height:768});assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.screenshot({path:output+'/verified-narrow.png',fullPage:true});
    await btn(p,'编辑理解与解释').click();await expect(dialog(p)).toBeVisible();await p.screenshot({path:output+'/verified-editor.png',fullPage:true});
  });
  await journey('observation history stays read only and real mode does not expose mock editing',async p=>{
    await p.goto(base+'#/observed-object?id=CL-001%401');await expect(p.locator('.observation-detail')).toContainText('CL-001@1');await btn(p,'前往评估模型管理 →').click();await expect(btn(p,'新建 Claim')).toBeVisible();await btn(p,'← 返回观测来源').click();await expect(p).toHaveURL(/observed-object/);
    await btn(p,'评估模型管理').click();await p.getByLabel('数据来源',{exact:true}).selectOption('real');await expect(p.getByRole('heading',{name:'尚未接入真实模型数据'})).toBeVisible();await expect(btn(p,'新建 Claim')).toHaveCount(0);
  });
});
