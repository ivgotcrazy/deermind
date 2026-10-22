import { test, expect, type Page } from '@playwright/test';
import type { LiveSession, LiveCommand } from '../src/structure/live';
const student='/structure.html?role=student';
const admin='/structure.html?role=admin';
async function model(page:Page) {
 const data:LiveSession={id:'REAL-integration-001',model:'protocol-test',chapter:'fractions',phase:'learning',check:null,turns:[],pending:null,error:null,updatedAt:new Date().toISOString()};
 const commands:LiveCommand[]=[];const ids=new Set<string>();
 await page.route('**/api/live/**',async route=>{
  if(route.request().url().endsWith('/commands')){
   const c=route.request().postDataJSON() as LiveCommand;
   if(!ids.has(c.requestId)){
    ids.add(c.requestId);commands.push(c);
    if(c.kind==='start_check'){data.phase='check';data.check='q-check';}
    else if(c.kind==='end')data.phase='ended';
    else if(c.kind==='resume')data.phase='learning';
    else {
     data.turns.push({id:`u${commands.length}`,role:'user',text:c.text||c.kind,at:new Date().toISOString()});
     if(c.kind==='check_request')data.turns.push({id:`a${commands.length}`,role:'assistant',blocks:[{type:'question',id:'q-check',mode:'check',state:'offered',prompt:'20 比 16 多几分之几？'}],at:new Date().toISOString()});
     else {if(c.kind==='help'){data.phase='learning';data.check=null;}data.turns.push({id:`a${commands.length}`,role:'assistant',blocks:[{type:'text',text:'比较时先找标准量。<img src=x onerror="window.injected=true">'}],suggestions:['换一种讲法'],at:new Date().toISOString()});}
    }
    data.updatedAt=new Date().toISOString();
   }
  }
  await route.fulfill({json:data});
 });
 return {data,commands};
}
test('new admin includes observation and retained publish/adoption safeguards',async({page})=>{
 await page.goto(admin+'#/maintenance');
 const publish=page.getByRole('button',{name:'发布候选 v2',exact:true});
 await expect(publish).toBeDisabled();
 await page.getByRole('textbox',{name:'参数与适用条件',exact:true}).fill('正数且单位一致，允许旋转，必须为对应高。');
 await page.getByRole('button',{name:'检查字段与引用'}).click();
 await page.getByLabel('人工审核结论').selectOption('pass');
 await page.getByRole('textbox',{name:'审核依据',exact:true}).fill('核对代表性案例与对应高。');
 await page.getByRole('button',{name:'记录批准'}).click();
 await expect(publish).toBeEnabled();
 await page.getByRole('textbox',{name:'名称',exact:true}).fill('旋转三角形面积');
 await expect(publish).toBeDisabled();
 await page.getByRole('button',{name:'检查字段与引用'}).click();await page.getByRole('button',{name:'记录批准'}).click();await publish.click();
 await page.reload();await expect(page.getByText('目录 v2 · 校内空间 v1',{exact:true})).toBeVisible();
 await page.getByLabel(/校内合成演示空间 · 当前 v1/).check();
 await page.getByRole('button',{name:'指定所选空间采用 v2'}).click();
 await expect(page.getByText('目录 v2 · 校内空间 v2',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'领域管理',exact:false}).click();
 await page.reload();await expect(page).toHaveURL(/#\/domain/);
 await page.getByRole('button',{name:'交互审查',exact:false}).click();
 await page.getByRole('button',{name:'详情 →',exact:true}).first().click();
 await expect(page).toHaveURL(/trace-detail/);
});
test('actual admin session is separate from example traces and requires purpose',async({page})=>{
 await model(page);await page.goto(student);
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('实际会话检查');
 await page.getByRole('button',{name:'发送',exact:true}).click();await expect(page.locator('.message-row:not(.user)')).toHaveCount(1);
 await page.goto(admin+'#/actual');await page.getByRole('button',{name:'选择会话'}).click();
 await expect(page.getByRole('button',{name:'按用途打开实际会话'})).toBeDisabled();
 await page.getByLabel('实际会话查阅用途').fill('验证原输入与显示的反馈');
 await page.getByRole('button',{name:'按用途打开实际会话'}).click();
 await expect(page.getByText('实际会话检查',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>Object.keys(JSON.parse(localStorage.getItem('deermind-structure-v1')!).access).length)).toBe(1);
});
test('admin account changes appear in the new user list and missing traces never show another learner',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(admin+'#/account');
 await page.getByLabel('已在系统外核实本人及本次操作所需关系').check();
 await page.getByLabel('身份核实依据').fill('本次仅核对合成账号的整合流程');
 await page.getByLabel('演示账号名称').fill('整合测试家长');
 await page.getByRole('button',{name:'创建合成账号档案',exact:true}).click();
 await page.getByRole('button',{name:'用户管理',exact:false}).click();
 await expect(page.getByText('整合测试家长',{exact:true})).toBeVisible();
 await page.reload();await expect(page.getByText('整合测试家长',{exact:true})).toBeVisible();
 await page.screenshot({path:'../../.tmp/integrated-admin-users.png'});
 for(const [path,heading] of [['evaluation','评估模型管理'],['textbooks','教材管理'],['targets','目标管理'],['learning-spaces','学习空间管理']]){
  await page.goto(admin+`#/${path}`);await expect(page.getByRole('heading',{name:heading!,exact:true})).toBeVisible();
 }
 await page.goto(admin+'#/trace-detail?id=missing');
 await expect(page.getByRole('heading',{name:'没有这条示例轨迹'})).toBeVisible();
 await expect(page.locator('.io-text')).toHaveCount(0);
 expect(errors).toEqual([]);
});
