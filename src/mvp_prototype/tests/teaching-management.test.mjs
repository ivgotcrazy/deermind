import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium, expect } from '@playwright/test';
import { createPrototypeServer } from '../scripts/serve.mjs';

const output=fileURLToPath(new URL('../../../.tmp/teaching-model-review-20261027/',import.meta.url));
await mkdir(output,{recursive:true});
const btn=(p,name)=>p.getByRole('button',{name,exact:true});
test('Teaching model mock authoring and conditional walkthroughs',async t=>{
  let modelCalls=0;
  const server=createPrototypeServer({directory:output,config:{key:'fixture',model:'mock'},provider:async()=>{modelCalls++;throw Error('No model call expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`;
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));assert.equal(modelCalls,0);});
  async function journey(name,run,hash='interaction'){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'}),p=await ctx.newPage(),errors=[],api=[];
      p.setDefaultTimeout(7000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))api.push(r.url());});
      try{await p.goto(base+'#/'+hash);await run(p);assert.deepEqual(errors,[]);assert.deepEqual(api,[]);}finally{await ctx.close();}
    });
  }
  const dialog=p=>p.getByRole('dialog');
  const division=(p,name)=>p.getByRole('navigation',{name:'教学模型分区'}).getByRole('button',{name,exact:true});

  await journey('new management entry is separate from observation and supports graph keyboard selection',async p=>{
    await expect(p.getByRole('group',{name:'模型管理',exact:true}).getByRole('button')).toHaveText(['领域空间','评估空间','交互空间']);
    await expect(p.locator('.teaching-graph .graph-node')).toHaveCount(6);
    await expect(p.locator('.teaching-graph .graph-edge')).toHaveCount(13);
    const phase=p.getByRole('button',{name:'阶段 5：检测与反馈',exact:true});await phase.focus();await p.keyboard.press('Enter');
    await expect(p.getByRole('complementary',{name:'蓝图定义详情'})).toContainText('实质求助先结束整个检测');
    await p.getByRole('button',{name:'连接：确定学习起点 → 检测与反馈，直接检验',exact:true}).locator('text').click();
    await expect(p.locator('.inspector')).toContainText('学生同意开始');
    await p.getByRole('button',{name:'阶段 3：讲解与互动',exact:true}).click();
    await p.screenshot({path:output+'/01-blueprint.png'});
    await btn(p,'空间观测').click();await p.getByRole('group',{name:'空间观测',exact:true}).getByRole('button',{name:'交互空间',exact:true}).click();
    await expect(p).toHaveURL(/objects.*tab=Interaction/);await expect(p.locator('.teaching-workspace')).toHaveCount(0);
    await p.getByRole('group',{name:'模型管理',exact:true}).getByRole('button',{name:'交互空间',exact:true}).click();await expect(p.locator('.teaching-workspace h2')).toHaveText('教学模型管理');
  });
  await journey('blueprint edit drafts cancel, persist across menus, save and mark old walkthroughs stale',async p=>{
    await btn(p,'编辑阶段').click();await dialog(p).getByLabel('阶段目的',{exact:true}).fill('取消内容');await btn(p,'取消').click();await expect(p.locator('.inspector')).not.toContainText('取消内容');
    await btn(p,'编辑阶段').click();await dialog(p).getByLabel('阶段目的',{exact:true}).fill('');await btn(p,'应用到草稿').click();await expect(dialog(p).getByRole('alert')).toBeFocused();
    await dialog(p).getByLabel('阶段目的',{exact:true}).fill('围绕当前疑问，用具体关系解释。');await btn(p,'应用到草稿').click();await expect(btn(p,'保存蓝图')).toBeEnabled();
    await p.getByRole('group',{name:'模型管理',exact:true}).getByRole('button',{name:'领域空间',exact:true}).click();
    await p.getByRole('group',{name:'模型管理',exact:true}).getByRole('button',{name:'交互空间',exact:true}).click();await expect(p.locator('.inspector')).toContainText('围绕当前疑问');
    await btn(p,'保存蓝图').click();await expect(p.locator('.page-header')).toContainText('v2');await expect(btn(p,'保存蓝图')).toBeDisabled();
    await btn(p,'情境推演').click();await expect(p.getByRole('status')).toContainText('规则已修改，示例待核对');
    await btn(p,'← 返回教学蓝图').click();await btn(p,'修改记录').click();await expect(dialog(p)).toContainText('保存蓝图：阶段「讲解与互动」');await btn(dialog(p),'关闭对话框').click();
    await btn(p,'编辑阶段').click();await dialog(p).getByLabel('阶段目的',{exact:true}).fill('准备放弃');await btn(p,'应用到草稿').click();await btn(p,'取消修改').click();await btn(p,'确认放弃').click();
    await p.getByRole('button',{name:'阶段 3：讲解与互动',exact:true}).click();await expect(p.locator('.inspector')).toContainText('围绕当前疑问');await expect(p.locator('.inspector')).not.toContainText('准备放弃');
  });
  await journey('adding stages and connections is editable; disconnected graph cannot be saved',async p=>{
    await btn(p,'添加阶段').click();await dialog(p).getByLabel('阶段名称',{exact:true}).fill('方法比较');await dialog(p).getByLabel('阶段目的',{exact:true}).fill('比较两种方法的条件');await dialog(p).getByLabel('需要的信息',{exact:true}).fill('两种方法与当前任务');await dialog(p).getByLabel('留下的结果',{exact:true}).fill('学生指出适用条件');await dialog(p).getByLabel('插入到哪条连接中').selectOption('teach-practice');await btn(p,'应用到草稿').click();
    await expect(p.locator('.graph-node')).toHaveCount(7);await btn(p,'保存蓝图').click();await expect(p.locator('.page-header')).toContainText('v2');
    await btn(p,'添加连接').click();await dialog(p).getByLabel('起点',{exact:true}).selectOption('entry');await dialog(p).getByLabel('终点',{exact:true}).selectOption('summary');await dialog(p).getByLabel('连接名称').fill('暂不继续');await dialog(p).getByLabel('转移条件').fill('学生决定停止');await dialog(p).getByLabel('判断依据').fill('当前学生请求');await btn(p,'应用到草稿').click();await btn(p,'保存蓝图').click();
    await expect(p.locator('.inspector')).toContainText('学生决定停止');
    await p.getByRole('button',{name:'连接：开始 → 明确本次学习重点，开始',exact:true}).locator('text').click();await btn(p,'编辑连接').click();await btn(p,'移除连接').click();await btn(p,'确认移除').click();await btn(p,'保存蓝图').click();await expect(p.getByRole('alert')).toContainText('无法从开始到达');
    await btn(p,'取消修改').click();await btn(p,'确认放弃').click();await expect(btn(p,'保存蓝图')).toBeDisabled();
    await btn(p,'编辑信息').click();await dialog(p).getByLabel('蓝图名称').fill('教学过程测试');await btn(p,'应用到草稿').click();await expect(p.locator('.blueprint-heading h3')).toHaveText('教学过程测试');await btn(p,'保存蓝图').click();
  });
  await journey('strategy sections share one definition and support create, edit and disable',async p=>{
    await btn(p,'对比辨析 ↗').click();await expect(p.locator('.strategy-heading')).toContainText('对比辨析');await expect(p.locator('.strategy-section')).toHaveCount(4);
    await btn(p,'编辑调整与结束').click();await dialog(p).getByLabel('调整方式',{exact:true}).fill('先核对学生所指的对象，再判断是否换教法。');await btn(p,'保存').click();await expect(p.locator('.strategy-section').filter({hasText:'调整与结束'})).toContainText('先核对学生所指的对象');
    await btn(p,'停用策略').click();await expect(p.locator('.strategy-heading')).toContainText('停用');await btn(p,'← 返回教学蓝图').click();await expect(p.locator('.strategy-links')).toContainText('已停用 · 不可选择');
    await division(p,'教学策略').click();await p.getByLabel('搜索策略').fill('对比');await expect(p.locator('.strategy-table tbody tr')).toHaveCount(1);await p.getByLabel('搜索策略').fill('');
    await btn(p,'新建策略').click();await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toBeFocused();
    for(const [label,value]of Object.entries({'策略名称':'结果合理性检查','教学目的':'检查结果是否合理','适用情况':'完成计算后','不适用情况':'题意尚未明确','如何组织教学':'先估计再与计算结果比较','需要观察的表现':'能解释数量关系','调整方式':'关系不清楚时返回解释','结束条件':'能指出结果与关系是否一致','依据与限制':'本次设计假设，待真实教学验证'}))await dialog(p).getByLabel(label,{exact:true}).fill(value);
    await btn(p,'保存').click();await expect(p.locator('.strategy-heading h3')).toHaveText('结果合理性检查');await expect(p.locator('.strategy-heading')).toContainText('v1');
    await division(p,'教学策略').click();await expect(p.locator('.strategy-table tbody tr')).toHaveCount(7);await p.screenshot({path:output+'/02-strategies.png'});
  });
  await journey('shared teaching rules can be edited while system constraints remain read-only',async p=>{
    await division(p,'通用规则').click();await btn(p,'新增规则').click();await btn(p,'保存').click();await expect(dialog(p).getByRole('alert')).toContainText('请填写');
    for(const [label,value]of Object.entries({'规则名称':'先回应明确疑问','适用情况':'学生已经说明卡点','具体要求':'直接围绕疑问解释','依据与限制':'产品设计假设'}))await dialog(p).getByLabel(label,{exact:true}).fill(value);
    await btn(p,'保存').click();const row=p.locator('.rule-table tbody tr').filter({hasText:'先回应明确疑问'});await expect(row).toContainText('直接围绕疑问解释');await btn(p,'停用规则：先回应明确疑问').click();await expect(row).toContainText('停用');
    await p.locator('.system-boundaries summary').click();await expect(p.locator('.system-boundaries')).toContainText('独立检测实质求助先结束检测');await expect(p.locator('.system-boundaries button,input,textarea')).toHaveCount(0);
    await p.screenshot({path:output+'/03-rules.png'});
  });
  await journey('foundation scenario distinguishes prerequisite repair from original-task mastery',async p=>{
    await btn(p,'情境推演').click();await btn(p,'下一轮').click();await expect(p.locator('.decision')).toContainText('概念建立与回补');await expect(p.locator('.teaching-figure circle')).toHaveCount(12);await btn(p,'下一轮').click();
    await btn(p,'仍把第二个分数用于 12 人 →').click();await expect(p.locator('.decision')).toContainText('对比辨析');await expect(p.locator('.stage-strip .active')).toContainText('讲解与互动');
    await btn(p,'上一轮').click();await btn(p,'能说明两层关系，愿意检测 →').click();await expect(p.locator('.conversation')).toContainText('6 本');await expect(p.locator('.decision')).toContainText('单题检测结束后才反馈');
    await btn(p,'下一轮').click();await expect(p.locator('.conversation')).toContainText('本次情境已收束');
  });
  await journey('explanation scenario changes strategy within a stage and returns from definition without losing the branch',async p=>{
    await btn(p,'情境推演').click();await btn(p,'会算但解释不清').click();await btn(p,'下一轮').click();await expect(p.locator('.decision')).toContainText('对比辨析');await btn(p,'希望直接听解释 →').click();await expect(p.locator('.conversation')).toContainText('4×3/4=3');await expect(p.locator('.conversation')).toContainText('12×3/4=9');
  });
  await journey('explanation scenario handles foundation switch, references and highlighted path',async p=>{
    await btn(p,'情境推演').click();await btn(p,'会算但解释不清').click();await btn(p,'下一轮').click();await btn(p,'仍认为两种说法相同 →').click();await expect(p.locator('.decision')).toContainText('概念回补');
    await btn(p,'查看当前策略定义 ↗').click();await expect(p.locator('.strategy-heading h3')).toHaveText('概念建立与回补');await btn(p,'← 返回情境推演').click();await expect(p.locator('.conversation h3')).toHaveText('同一阶段内换教法');
    await btn(p,'展开蓝图路径与来源规则').click();await expect(p.locator('.scene-graph .graph-node.active')).toHaveCount(1);await p.getByRole('button',{name:'连接：确定学习起点 → 讲解与互动，需要讲解',exact:true}).locator('text').click();await expect(p.locator('.scene-graph .inspector')).toContainText('请求或实际表现');
    await p.screenshot({path:output+'/04-scenario-explanation.png'});
    await btn(p,'下一轮').click();await expect(p.locator('.stage-strip .active')).toContainText('练习与应用');await btn(p,'下一轮').click();await expect(p.locator('.conversation')).toContainText('延迟保持');
  });
  await journey('transfer walkthrough separates success, remediation, material ambiguity and help',async p=>{
    await btn(p,'情境推演').click();await btn(p,'已理解，检验迁移').click();await btn(p,'下一轮').click();await btn(p,'12 平方米，并解释清楚 →').click();await expect(p.locator('.conversation')).toContainText('本次单题检测结束');await expect(p.locator('.conversation')).toContainText('所有迁移或持久性');
    await btn(p,'上一轮').click();await btn(p,'20 平方米，参照数量混淆 →').click();await expect(p.locator('.conversation')).toContainText('这次单题检测已结束');await expect(p.locator('.decision')).toContainText('对比辨析');
    await btn(p,'上一轮').click();await btn(p,'图示存在歧义 →').click();await expect(p.locator('.decision')).toContainText('不判错');await expect(p.locator('.conversation')).toContainText('暂不能形成能力结论');
    await btn(p,'上一轮').click();await btn(p,'请求讲解，先结束检测 →').click();await expect(p.locator('.conversation')).toContainText('未提交的部分保持未检测');await expect(p.locator('.decision')).toContainText('不恢复原检测');await expect(p.getByRole('img',{name:/花坛分区示意图/})).toBeVisible();await p.screenshot({path:output+'/05-scenario-help.png',fullPage:true});
  });
  await journey('new page is mock-only and fits desktop and smaller review viewports',async p=>{
    await p.setViewportSize({width:1100,height:850});await expect(p.locator('.inspector h3')).toHaveText('讲解与互动');await p.screenshot({path:output+'/06-blueprint-1100.png'});
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await p.getByLabel('数据来源').selectOption('real');await expect(p.getByRole('heading',{name:'尚未接入真实模型数据'})).toBeVisible();await expect(p.locator('.teaching-workspace')).toHaveCount(0);
    await btn(p,'切换到示例走查').click();await expect(p.locator('.teaching-workspace')).toBeVisible();
  });
});
