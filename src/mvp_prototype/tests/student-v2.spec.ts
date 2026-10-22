import { test, expect, type Page } from '@playwright/test';
import type { LiveSession, LiveCommand } from '../src/structure/live';
const student='/structure.html?role=student';
export async function model(page:Page) {
 const data:LiveSession={id:'REAL-v2-context-001',model:'protocol-test',chapter:'fractions',phase:'learning',check:null,turns:[],pending:null,error:null,updatedAt:new Date().toISOString()};
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
     if(['check_request','practice_request'].includes(c.kind))data.turns.push({id:`a${commands.length}`,role:'assistant',blocks:[{type:'question',id:c.kind==='check_request'?'q-check':'q-practice',mode:c.kind==='check_request'?'check':'practice',state:'offered',prompt:'20 比 16 多几分之几？'}],at:new Date().toISOString()});
     else {if(c.kind==='help'||c.kind==='answer'){data.phase='learning';data.check=null;for(const t of data.turns)for(const b of t.blocks||[])if(b.type==='question')b.state=c.kind==='help'?'helped':'answered';}data.turns.push({id:`a${commands.length}`,role:'assistant',blocks:[{type:'text',text:'比较时先找标准量。<img src=x onerror="window.injected=true">'}],suggestions:['换一种讲法'],at:new Date().toISOString()});}
    }
    data.updatedAt=new Date().toISOString();
   }
  }
  await route.fulfill({json:data});
 });
 return {data,commands};
}
async function send(page:Page,text='为什么要除以比较标准？') {
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill(text);
 await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('.message-row:not(.user)')).toHaveCount(1);
}
for(const [id,label] of [['home','首页'],['status','学习情况'],['textbook','教材'],['errorbook','错题本']]) {
 test(`V2 ${label} starts conversation without replacing source page`,async({page})=>{
  const m=await model(page);await page.goto(`${student}#/${id}`);
  await send(page);
  await expect(page).toHaveURL(new RegExp(`#/${id}\\?chat=`));
  await expect(page.getByLabel(`页面上下文：${label}`)).toBeVisible();
  expect(m.commands[0]!.context).toEqual({page:id,label});
  expect(m.commands[0]!.text).toBe('为什么要除以比较标准？');
  const left=await page.locator('.chat-pane').boundingBox(),right=await page.locator('.static-pane').boundingBox();
  expect(left!.x+left!.width).toBeLessThanOrEqual(right!.x+1);
  await expect(page.locator('.static-pane h2').filter({hasText:label==='首页'?'数学':label}).first()).toBeVisible();
 });
}
test('V2 context selection, collapse, navigation, history and reload retain one conversation and drafts',async({page})=>{
 const m=await model(page);await page.goto(student+'#/status');
 await page.getByLabel('查找章节',{exact:true}).fill('分数的应用');
 await page.locator('.chapter-card').filter({hasText:'分数的应用'}).click();
 await page.getByRole('button',{name:'请帮我讲讲',exact:true}).click();
 await expect(page.locator('.message-row:not(.user)')).toHaveCount(1);
 await expect(page.getByRole('button',{name:'返回章节概览',exact:false})).toBeVisible();
 await page.getByLabel('向真实 DeerMind 提问').fill('保留追问');
 await page.getByLabel('收起聊天',{exact:true}).click();
 await expect(page.locator('.messages-container')).toHaveCount(0);
 await expect(page.getByLabel('向真实 DeerMind 提问')).toHaveValue('保留追问');
 await page.reload();await expect(page.getByLabel('向真实 DeerMind 提问')).toHaveValue('保留追问');
 await page.getByLabel('展开聊天',{exact:true}).click();
 await page.getByRole('button',{name:'教材',exact:true}).click();
 await expect(page.getByLabel('页面上下文：教材')).toBeVisible();
 await expect(page.locator('.message-row:not(.user)')).toHaveCount(1);
 await page.getByRole('button',{name:'学习情况',exact:true}).click();
 await page.getByRole('button',{name:'返回章节概览',exact:false}).click();
 await expect(page.getByLabel('查找章节',{exact:true})).toHaveValue('分数的应用');
 await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect.poll(()=>m.commands.length).toBe(2);
 await page.getByRole('button',{name:'结束 ×',exact:true}).click();
 await expect(page.locator('.chat-pane')).toHaveCount(0);
 await expect(page.getByLabel('页面上下文：学习情况')).toBeVisible();
 await page.getByLabel('查看对话历史').click();
 await page.getByRole('button',{name:'继续这次交流',exact:true}).click();
 await page.getByRole('button',{name:'继续这次交流',exact:true}).click();
 await expect(page.getByLabel('向真实 DeerMind 提问')).toBeVisible();
 await page.goto(student+'#/lesson?id='+m.data.id);
 await expect(page).toHaveURL(/#\/status\?chat=REAL-v2-context-001/);
 await expect(page.locator('.message-row:not(.user)')).toHaveCount(2);
});
test('inline practice and check keep context; help ends check before restoring reference',async({page})=>{
 const m=await model(page);await page.goto(student+'#/textbook');await send(page);
 await page.getByRole('button',{name:'出一道练习',exact:true}).click();
 await page.getByLabel('练习答案',{exact:true}).fill('1/4，因为相差4，以16为标准');
 await page.reload();await expect(page.getByLabel('练习答案')).toHaveValue('1/4，因为相差4，以16为标准');
 await page.getByRole('button',{name:'提交这道练习',exact:true}).click();
 await page.getByRole('button',{name:'检查这次理解',exact:true}).click();
 await page.getByRole('button',{name:'开始这道检查',exact:true}).click();
 await expect(page.locator('.page-host')).toBeHidden();
 await page.getByLabel('检查答案',{exact:true}).fill('还不确定');
 await page.getByRole('button',{name:'学习情况',exact:true}).click();
 await expect(page).toHaveURL(/#\/textbook\?chat=/);
 await page.reload();await expect(page.getByLabel('检查答案',{exact:true})).toHaveValue('还不确定');
 await page.getByRole('button',{name:'求助并结束检查',exact:true}).click();
 await expect(page.locator('.page-host')).toBeVisible();
 await expect(page.getByLabel('向真实 DeerMind 提问')).toBeVisible();
 expect(m.commands.at(-1)!.kind).toBe('help');expect(m.data.phase).toBe('learning');
});
test('safe text, failed delivery and idempotent recovery preserve raw draft',async({page})=>{
 const m=await model(page);let failed=false;
 await page.route('**/commands',async route=>{if(!failed){failed=true;await route.abort('failed');}else await route.fallback();});
 await page.goto(student);await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('<span id="injected">这是文本</span>');
 await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.getByRole('button',{name:'确认或重发同一请求'})).toBeVisible();
 await expect(page.getByLabel('向真实 DeerMind 提问')).toHaveValue('<span id="injected">这是文本</span>');
 const before=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-structure-v1')!).drafts['real-request:REAL-v2-context-001']);
 await page.reload();await expect(page.locator('.message-row:not(.user)')).toHaveCount(1);
 expect(m.commands[0]!.requestId).toBe(JSON.parse(before).requestId);
 expect(await page.locator('#injected').count()).toBe(0);expect(await page.evaluate(()=>('injected' in window))).toBeFalsy();
 expect(m.commands).toHaveLength(1);
});
test('classroom progress and picture records persist and remain isolated by space',async({page})=>{
 await page.goto(student);await page.getByLabel('设置课堂进度').click();
 await page.getByRole('checkbox',{name:/分数的应用/}).check();await page.getByRole('button',{name:'保存课堂进度'}).click();
 await page.reload();await expect(page.getByLabel('课堂进度',{exact:true})).toContainText('分数的应用');
 await page.locator('input[type=file]').setInputFiles({name:'problem.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jvWQAAAAASUVORK5CYII=','base64')});
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('拍照题目说明');await page.getByRole('button',{name:'保存题目输入',exact:true}).click();
 await page.getByRole('button',{name:'错题本',exact:true}).click();await page.getByRole('button',{name:'待处理输入',exact:true}).click();
 await expect(page.getByText('拍照题目说明',{exact:true})).toBeVisible();await page.reload();await expect(page.getByText('拍照题目说明',{exact:true})).toBeVisible();
 await page.getByLabel('当前学习空间').click();await page.getByRole('button',{name:'📖 校外数学',exact:true}).click();
 await page.getByRole('button',{name:'错题本',exact:true}).click();await page.getByRole('button',{name:'待处理输入',exact:true}).click();
 await expect(page.getByText('拍照题目说明',{exact:true})).toHaveCount(0);
 await page.goto('/structure.html?role=parent#/overview');await page.getByLabel('查看课堂进度').click();
 await expect(page.getByRole('dialog')).toContainText('分数的应用');await expect(page.getByRole('button',{name:'保存课堂进度'})).toHaveCount(0);
});
test('V2 layout at desktop/tablet/phone keeps conversation and source page available',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await model(page);await page.goto(student);
 for(const size of [{width:1280,height:900},{width:834,height:1112},{width:390,height:844}]){
  await page.setViewportSize(size);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const main=await page.locator('.main-content').boundingBox(),input=await page.locator('.bottom-bar-host').boundingBox();
  expect(main!.y+main!.height).toBeLessThanOrEqual(input!.y+1);
  await page.screenshot({path:`../../.tmp/v2-rebase/home-${size.width}.png`});
 }
 await send(page);
 for(const size of [{width:1280,height:900},{width:834,height:1112},{width:390,height:844}]){
  await page.setViewportSize(size);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const left=await page.locator('.chat-pane').boundingBox(),right=await page.locator('.static-pane').boundingBox();
  if(size.width>700)expect(left!.x+left!.width).toBeLessThanOrEqual(right!.x+1);
  else expect(left!.y+left!.height).toBeLessThanOrEqual(right!.y+1);
  const scroll=await page.locator('.messages-container').boundingBox(),input=await page.locator('.composer-wrapper').boundingBox();
  expect(scroll!.y+scroll!.height).toBeLessThanOrEqual(input!.y+1);
  expect(right!.height).toBeGreaterThan(100);
  await page.screenshot({path:`../../.tmp/v2-rebase/chat-${size.width}.png`});
 }
 expect(errors).toEqual([]);
});
