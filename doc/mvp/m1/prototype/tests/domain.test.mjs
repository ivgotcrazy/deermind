import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium, expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

const expect=baseExpect.configure({timeout:8000});
const output=fileURLToPath(new URL('../test-results/domain/',import.meta.url));
test('M1 manual domain authoring and explicit mock checks',async t=>{
  const server=createPreviewServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
  const page=await context.newPage();page.setDefaultTimeout(8000);
  const errors=[],api=[],screens=[];
  page.on('pageerror',error=>errors.push(error.message));
  await context.route('**/api/**',route=>{api.push(route.request().url());return route.abort();});
  t.after(async()=>{await browser.close();await new Promise(resolve=>server.close(resolve));});
  await mkdir(output,{recursive:true});
  const btn=name=>page.getByRole('button',{name,exact:true});
  const label=name=>page.getByLabel(name,{exact:true});
  const state=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')));
  const open=async(d,kind='task',id='',tab='')=>{
    await page.goto(base+'/admin/#/domain?'+new URLSearchParams({domain:d,kind,...(id?{id}:{}),...(tab?{tab}:{})}));
    await expect(page.locator('.domain-workspace')).toBeVisible();
  };
  const shot=async(name)=>{await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:output+name+'.png',animations:'disabled'});screens.push(name);};
  let domainId,taskId,kcId,methodId,instanceId;
  await page.goto(base+'/admin/#/textbooks');
  await btn('导入教材').click();
  await label('教材名称').fill('原有教材草稿');
  const imports=await page.evaluate(()=>localStorage.getItem('deermind-m1-import-v1'));

  await t.test('create an empty domain, a KC and a task through visible controls',async()=>{
    await page.getByRole('navigation',{name:'后台导航'}).getByRole('button',{name:/领域管理/}).click();
    await expect(page.getByText('从一个空领域开始',{exact:true})).toBeVisible();
    await btn('新建领域').click();
    await label('领域名称').fill('手动创建的小学数学');await label('覆盖范围').fill('比例增加任务与知识');
    await btn('创建并进入').click();
    await expect(page.getByRole('heading',{name:'手动创建的小学数学',exact:true})).toBeVisible();
    domainId=(await state()).domains[0].id;
    await page.getByRole('navigation',{name:'领域对象'}).getByRole('button',{name:/知识成分/}).click();
    await btn('新建知识成分').click();await label('知识名称').fill('原量与增加量的关系');
    await label('定义与含义').fill('新量等于原量加上增加量。');await label('适用条件').fill('比例以原量为基准，单位一致。');
    await label('示例与边界说明').fill('40米增加四分之一得到50米。');await btn('保存知识').click();
    await expect(page.getByRole('heading',{name:'原量与增加量的关系',exact:true})).toBeVisible();
    kcId=(await state()).knowledge[0].id;
    await btn('编辑知识').click();await label('知识名称').fill('不应保存的修改');await btn('取消').click();
    assert.equal((await state()).knowledge[0].name,'原量与增加量的关系');
    await open(domainId);await btn('新建任务模板').click();
    await label('任务名称').fill('手动：已知原量和增加比例求新量');await label('任务说明').fill('识别整体并计算新量。');
    await label('任务目标').fill('求新量 W');await label('学习者承担的工作').fill('选择方法，计算并解释数量关系。');await btn('添加完成要求').click();await label('要求1交付内容').fill('数量、单位和说明');await label('要求1完成条件').fill('数量与题设关系一致，单位正确并解释比例的参照量。');
    await btn('创建任务模板').click();await expect(page.getByRole('heading',{name:'手动：已知原量和增加比例求新量',exact:true})).toBeVisible();
    taskId=(await state()).tasks[0].id;
    await btn('编辑对象与变量').click();
    for(const [index,p] of [['V','原量','题目已给定','V > 0'],['r','增加比例','题目已给定','r > 0，无量纲'],['W','新量','需要研究或求解','与 V 同单位']].entries()){
      await btn('添加对象或变量').click();await label('对象'+(index+1)+'标识').fill(p[0]);await label('对象'+(index+1)+'名称').fill(p[1]);await label('对象'+(index+1)+'类型').selectOption('数值');await label('对象'+(index+1)+'用途').selectOption(p[2]);await label('对象'+(index+1)+'约束').fill(p[3]);
    }
    await btn('保存修改').click();
    for(const [section,value] of [['条件与关系','增加量 / V = r；W = V + 增加量'],['适用边界','不包含减少、反求原量、连续多次变化']]){
      await btn('编辑'+section).click();await label(section).fill(value);await btn('保存修改').click();
    }
    await btn('编辑允许的变化').click();await btn('添加变化').click();await label('变化1对象').fill('原量与比例');await label('变化1范围').fill('合法的原量、比例及单位');await label('变化1条件').fill('单位一致，比例参照原量。');await btn('保存修改').click();
    await page.getByRole('navigation',{name:'任务内容'}).getByRole('button',{name:'知识',exact:true}).click();
    await expect(page.getByText('没有可汇总的知识。请在方法中补齐知识依据。')).toBeVisible();
    assert.equal((await state()).tasks[0].methods.length,0);
  });

  await t.test('create and connect a method; knowledge is derived and survives reload',async()=>{
    await open(domainId,'solution');await btn('新建方法模板').click();
    await label('方法名称').fill('手动：先求增加量再相加');await label('方法思路').fill('先乘后加。');await label('适用条件').fill('比例对应原量。');await label('输入').fill('V、r');await label('输出').fill('W');
    await label('手动：已知原量和增加比例求新量').check();await btn('添加步骤').click();
    await label('步骤1名称').fill('计算新量');await label('步骤1处理').fill('计算 Δ = V × r，输出 W = V + Δ。');
    await label('步骤1输入').fill('V：原量；r：增加比例');await label('步骤1输出').fill('W：新量与单位');
    await label('成功完成').fill('数量关系和单位正确。');await label('无法继续时停止').fill('输入不足、比例整体不明时停止。');
    await label('原量与增加量的关系').check();await btn('保存方法').click();
    await expect(page.getByRole('heading',{name:'手动：先求增加量再相加',exact:true})).toBeInViewport();
    methodId=(await state()).methods[0].id;
    await open(domainId,'task',taskId,'knowledge');
    await expect(page.locator('.data-table tbody tr')).toHaveCount(1);await expect(page.locator('.data-table')).toContainText('手动：先求增加量再相加');
    await page.reload();await expect(page.locator('.data-table tbody tr')).toHaveCount(1);
    assert.deepEqual((await state()).tasks[0].methods,[methodId]);
    await btn('原量与增加量的关系').click();
    await expect(page.getByRole('heading',{name:'通过方法涉及这项知识的任务'})).toBeVisible();
    await expect(btn('手动：已知原量和增加比例求新量 →')).toBeVisible();
    await shot('01-knowledge-links');
  });

  await t.test('instance draft, failed semantic checks and successful mock check; no answer in student preview',async()=>{
    await open(domainId,'task',taskId,'instances');await btn('新建题目').click();
    await label('题目内容').fill('原长40米，增加原长的四分之一，共长多少米？请说明理由。');
    await btn('检查并保存为可用题').click();await expect(page.getByRole('alert')).toContainText('请填写所有题目已给定信息');
    await label('绑定参数 V').fill('40 米');await label('绑定参数 r').fill('1/4');
    await label('参考答案／评分要点').fill('50米；40+40×1/4。');await label('手动：先求增加量再相加').check();
    await label('手动：先求增加量再相加的具体解答').fill('40×1/4=10，40+10=50米。');await label('来源说明').fill('作者手动编写用于走查');
    await btn('添加表格').click();await label('题面表格1行1列').fill('40米');await label('题面表格1行2列').fill('1/4');
    await btn('预览学生题面').click();
    await expect(page.getByTestId('student-question')).toContainText('40米');await expect(page.getByTestId('student-question')).not.toContainText('50');await expect(page.getByRole('dialog')).not.toContainText('参考答案');
    await shot('02-student-question');await btn('返回编辑').click();
    await page.getByText('模拟语义检查结果',{exact:true}).click();
    for(const result of ['mismatch','unclear','answer']){
      await label('本次模拟结果').selectOption(result);await btn('检查并保存为可用题').click();await expect(page.getByRole('alert')).toContainText('模拟检查');
      assert.equal((await state()).instances.length,0);
    }
    await shot('03-check-failure');await btn('保存草稿').click();
    await expect(page.locator('.data-table')).toContainText('待检查');instanceId=(await state()).instances[0].id;
    await page.reload();await btn('编辑题目 '+instanceId).click();await btn('检查并保存为可用题').click();
    await expect(page.locator('.data-table')).toContainText('可用（mock）');await shot('04-instances');
    await open(domainId,'kc',kcId);await btn('编辑知识').click();await label('定义与含义').fill('新量等于原量加增加量。此处修改用于核对检查是否过期。');await btn('保存知识').click();
    await open(domainId,'task',taskId,'instances');await expect(page.locator('.data-table')).toContainText('需重新检查');
    assert.equal(await page.evaluate(()=>localStorage.getItem('deermind-m1-import-v1')),imports);
  });

  let sampleId,sampleTask,a,b,subTask;
  await t.test('example shows two alternatives, recursive dependencies and scoped domain lists',async()=>{
    await page.goto(base+'/admin/#/domain');await btn('载入示例领域').click();await btn('打开示例 primary').click();
    await expect(page.getByRole('heading',{name:'小学数学 · 示例'})).toBeVisible();
    const data=await state();sampleId=data.domains.find(d=>d.name==='小学数学 · 示例').id;
    sampleTask=data.tasks.find(x=>x.domainId===sampleId&&x.name==='已知原量和增加比例，求新量').id;
    subTask=data.tasks.find(x=>x.domainId===sampleId&&x.name==='求一个量的几分之几').id;
    a=data.methods.find(x=>x.domainId===sampleId&&x.name==='先求增加量，再加原量').id;
    b=data.methods.find(x=>x.domainId===sampleId&&x.name==='按原量的 1+r 倍计算').id;
    await shot('05-domain-tasks');await btn('已知原量和增加比例，求新量').click();await shot('06-task-definition');
    await page.getByRole('navigation',{name:'任务内容'}).getByRole('button',{name:'方法',exact:true}).click();
    await expect(page.locator('.data-table tbody tr')).toHaveCount(2);await shot('07-task-methods');
    await page.getByRole('navigation',{name:'任务内容'}).getByRole('button',{name:'知识',exact:true}).click();
    await expect(page.locator('.data-table tbody tr')).toHaveCount(3);await expect(page.locator('.data-table')).toContainText('使用分数乘法求对应数量');await shot('08-task-knowledge');
    await open(sampleId,'solution',a);await shot('09-recursive-method');
    await btn('编辑方法').click();await expect(label('手动：已知原量和增加比例求新量')).toHaveCount(0);await expect(label('原量与增加量的关系')).toHaveCount(0);await btn('取消').click();
    await open(domainId,'task',sampleTask);await expect(page.getByRole('heading',{name:'未找到这个对象'})).toBeVisible();
    await page.goto(base+'/admin/#/domain?domain=missing');await expect(page.getByRole('heading',{name:'未找到这个领域'})).toBeVisible();
  });

  await t.test('missing child method and indirect recursion are explained without freezing the page',async()=>{
    await open(sampleId,'solution',a);await btn('编辑方法').click();
    await label('步骤1子方法').selectOption('');await btn('保存方法').click();
    await expect(page.getByRole('status').filter({hasText:'方法尚未完整'})).toContainText('尚未选择子方法');
    await open(sampleId,'task',sampleTask,'instances');const sample=(await state()).instances.find(q=>q.domainId===sampleId);
    await btn('编辑题目 '+sample.id).click();await btn('检查并保存为可用题').click();await expect(page.getByRole('alert')).toContainText('尚未选择子方法');await btn('关闭对话框').click();
    await open(sampleId,'solution',a);await btn('编辑方法').click();await label('步骤1子任务').selectOption(sampleTask);await label('步骤1子方法').selectOption(b);await btn('保存方法').click();
    await open(sampleId,'solution',b);await btn('编辑方法').click();await label('步骤1分解为子任务').check();await label('步骤1子任务').selectOption(sampleTask);await label('步骤1子方法').selectOption(a);await btn('保存方法').click();
    await expect(page.getByRole('status').filter({hasText:'方法尚未完整'})).toContainText('方法循环');await expect(page.getByRole('status').filter({hasText:'方法尚未完整'})).toBeInViewport();await shot('10-cycle-feedback');
    await open(sampleId,'task',sampleTask,'knowledge');await expect(page.locator('.callout.amber')).toContainText('方法循环');
    // Break the cycle and restore the original child mapping through the editor.
    await open(sampleId,'solution',b);await btn('编辑方法').click();await label('步骤1分解为子任务').uncheck();await btn('保存方法').click();
    await open(sampleId,'solution',a);await btn('编辑方法').click();await label('步骤1子任务').selectOption(subTask);
    const child=(await state()).tasks.find(x=>x.id===subTask).methods[0];await label('步骤1子方法').selectOption(child);await btn('保存方法').click();
    await expect(page.getByRole('status').filter({hasText:'方法尚未完整'})).toHaveCount(0);
    await open(sampleId,'task',subTask);await btn('编辑适用边界').click();
    const boundary=await label('适用边界').inputValue();await label('适用边界').fill('');await btn('保存修改').click();
    await open(sampleId,'solution',a);await expect(page.getByRole('status').filter({hasText:'方法尚未完整'})).toContainText('缺少适用边界');
    await open(sampleId,'task',subTask);await btn('编辑适用边界').click();await label('适用边界').fill(boundary);await btn('保存修改').click();
  });

  await t.test('task method unlinking changes derived KC, invalidates instances, and definitions stay isolated',async()=>{
    await open(domainId,'task',taskId,'methods');await btn('关联方法').click();await label('手动：先求增加量再相加').uncheck();await btn('保存关联').click();
    await page.getByRole('navigation',{name:'任务内容'}).getByRole('button',{name:'知识',exact:true}).click();await expect(page.getByText('没有可汇总的知识。请在方法中补齐知识依据。')).toBeVisible();
    await open(domainId,'task',taskId,'instances');await btn('编辑题目 '+instanceId).click();await btn('检查并保存为可用题').click();await expect(page.getByRole('alert')).toContainText('参考方法不在当前任务');await btn('关闭对话框').click();
    await open(domainId);await btn('编辑领域').click();await label('覆盖范围').fill('更新后的课程无关领域范围');await btn('保存领域').click();await page.reload();await expect(page.getByText('更新后的课程无关领域范围',{exact:true})).toBeVisible();
    await open(sampleId,'task',sampleTask);await page.setViewportSize({width:1280,height:900});
    assert.equal(await page.locator('.page-container').evaluate(el=>el.scrollWidth>el.clientWidth+1),false);
    await page.getByRole('navigation',{name:'后台导航'}).getByRole('button',{name:/教材管理/}).click();await expect(page.getByText('原有教材草稿',{exact:true})).toBeVisible();
    assert.deepEqual(errors,[]);assert.deepEqual(api,[]);
  });
  await writeFile(output+'review.json',JSON.stringify({screens,errors,api,scope:'UI-only mock; no documentation changes; no OCR or LLM verification'},null,2));
});
