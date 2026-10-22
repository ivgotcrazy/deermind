import { test, expect, type Page } from '@playwright/test';
import type { LiveSession, LiveCommand } from '../src/structure/live';
const entry='/legacy-structure.html?role=student#/chapter?chapter=fractions';
async function mock(page:Page){
 const session:LiveSession={id:'REAL-test-session-001',model:'offline-test',chapter:'fractions',phase:'learning',check:null,turns:[],pending:null,error:null,updatedAt:new Date().toISOString()};
 let calls=0;
 await page.route('**/api/live/**',async route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.pathname.endsWith('/commands')){
   const c=request.postDataJSON() as LiveCommand;calls++;
   if(c.kind==='start_check'){session.check='question-check-1';session.phase='check';}
   else if(c.kind==='end'){session.phase='ended';}
   else if(c.kind==='resume'){session.phase='learning';}
   else {
    session.turns.push({id:`u${calls}`,role:'user',text:c.text||c.kind,at:new Date().toISOString()});
    if(c.kind==='check_request')session.turns.push({id:`a${calls}`,role:'assistant',blocks:[{type:'question',id:'question-check-1',mode:'check',prompt:'20 比 16 多几分之几？',state:'offered'}],suggestions:[],at:new Date().toISOString()});
    else if(c.kind==='help'){session.check=null;session.phase='learning';session.turns.push({id:`a${calls}`,role:'assistant',blocks:[{type:'text',text:'检查已结束，比较的标准是16。'}],suggestions:[],at:new Date().toISOString()});}
    else session.turns.push({id:`a${calls}`,role:'assistant',blocks:[{type:'text',text:'这是根据刚才问题生成的回复：<script>window.bad=true</script>'},{type:'formula',text:'3 ÷ 9 = 1/3'},{type:'bars',caption:'比较数量',rows:[{label:'甲',value:12},{label:'乙',value:9}]}],suggestions:['换一种讲法'],at:new Date().toISOString()});
   }
   session.updatedAt=new Date().toISOString();
  }
  await route.fulfill({json:session});
 });return {session,calls:()=>calls};
}
test('legacy entry continues in the dialogue workspace without sending synthetic history or losing drafts',async({page})=>{
 const m=await mock(page);await page.goto(entry.replace('?role=student','?role=student&preview=scripted'));await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();const old=page.url();
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('旧活动未发送的草稿');
 await page.goto(old.replace('&preview=scripted',''));await expect(page.getByRole('region',{name:'真实模型学习对话'})).toBeVisible();expect(page.url()).not.toBe(old);await expect(page.getByLabel('向真实 DeerMind 提问')).toHaveValue('旧活动未发送的草稿');expect(m.calls()).toBe(0);expect(m.session.turns).toHaveLength(0);
 await page.getByLabel('向真实 DeerMind 提问').fill('为什么比较标准会变？');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.locator('.live-turn.assistant')).toContainText('根据刚才问题');await expect(page.getByRole('figure',{name:'比较数量'})).toBeVisible();expect(await page.evaluate(()=>('bad' in window))).toBeFalsy();
 await page.getByLabel('向真实 DeerMind 提问').fill('未提交的追问');await page.reload();await expect(page.getByLabel('向真实 DeerMind 提问')).toHaveValue('未提交的追问');await expect(page.locator('.live-turn.assistant')).toHaveCount(1);
 const sessions=await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-structure-v1')!).sessions);expect(sessions).toHaveLength(2);expect(sessions.filter((s:any)=>s.real)).toHaveLength(1);expect(m.calls()).toBe(1);
 await page.getByRole('button',{name:'这次先到这里',exact:true}).click();await expect(page.getByRole('heading',{name:'这次交流已保存'})).toBeVisible();await page.getByRole('button',{name:'继续这次交流',exact:true}).click();await expect(page.getByLabel('向真实 DeerMind 提问')).toHaveValue('未提交的追问');
 await page.getByRole('button',{name:'返回首页',exact:true}).click();await page.getByRole('button',{name:'学习记录',exact:true}).click();await page.getByRole('button',{name:'学习活动',exact:true}).click();await page.getByRole('button').filter({hasText:'真实模型对话'}).click();await page.getByRole('button',{name:'回看真实对话',exact:true}).click();await expect(page.getByLabel('向真实 DeerMind 提问')).toHaveValue('未提交的追问');
 await page.goto(old.replace('&preview=scripted',''));await expect(page.getByLabel('向真实 DeerMind 提问')).toHaveValue('未提交的追问');expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-structure-v1')!).sessions.length)).toBe(2);
});

test('ordinary chapter entry opens the conversation directly with no second mode choice or surrounding navigation',async({page})=>{
 const m=await mock(page);await page.goto(entry);await expect(page.getByRole('button',{name:'开始真实对话',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();await expect(page.getByLabel('向真实 DeerMind 提问')).toBeVisible();await expect(page.getByRole('navigation',{name:'主导航'})).toHaveCount(0);await expect(page.locator('.learner-header')).toHaveCount(0);expect(m.calls()).toBe(0);
 await page.getByRole('button',{name:'返回首页',exact:true}).click();await expect(page.getByRole('navigation',{name:'主导航'})).toBeVisible();await page.getByRole('button',{name:/继续这次学习/}).click();await expect(page.getByLabel('向真实 DeerMind 提问')).toBeVisible();
});
test('check is embedded, hides teaching, restores answer draft and ends before help appears',async({page})=>{
 await mock(page);await page.goto(entry);await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();
 await page.getByRole('button',{name:'为什么要除以比较的标准量？'}).click();await page.getByRole('button',{name:'检查这次理解',exact:true}).click();
 await page.getByRole('button',{name:'开始这道检查',exact:true}).click();const url=page.url();await expect(page.locator('.live-turn')).toHaveCount(1);await expect(page.getByLabel('向真实 DeerMind 提问')).toHaveCount(0);await expect(page.locator('.live-composer').getByLabel('检查答案',{exact:true})).toBeVisible();
 await page.getByLabel('检查答案',{exact:true}).fill('我不确定比较标准');await page.reload();await expect(page.getByLabel('检查答案',{exact:true})).toHaveValue('我不确定比较标准');
 await page.getByRole('button',{name:'求助并结束检查',exact:true}).click();await expect(page.getByText('检查已结束，比较的标准是16。',{exact:true})).toBeVisible();await expect(page.getByLabel('检查答案',{exact:true})).toHaveCount(0);await expect(page).toHaveURL(url);
});
test('tablet and narrow screens keep the real composer outside scrolling teaching content',async({page})=>{
 await mock(page);await page.goto(entry);await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();await page.getByRole('button',{name:'为什么要除以比较的标准量？'}).click();
 for(const size of [{width:1280,height:800},{width:800,height:1280},{width:390,height:844}]){
  await page.setViewportSize(size);const bounds=await page.locator('.live-scroll').boundingBox(),composer=await page.locator('.live-composer').boundingBox();expect(bounds&&composer&&bounds.y+bounds.height<=composer.y+1).toBeTruthy();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.screenshot({path:`../../.tmp/mvp-dialogue-${size.width}.png`});
 }
});
