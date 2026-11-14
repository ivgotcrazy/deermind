import { chromium, expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';
export const expect=baseExpect.configure({timeout:8000});
export async function setup(t){
 const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'msedge'});
 const page=await browser.newPage({viewport:{width:1440,height:1000},locale:'zh-CN'});page.setDefaultTimeout(8000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
 const base='http://127.0.0.1:'+server.address().port;
 const btn=name=>page.getByRole('button',{name,exact:true});
 const state=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')));
 const open=async(domain,kind='task',id='',tab='definition')=>page.goto(base+'/admin/#/domain?'+new URLSearchParams({domain,kind,id,tab}));
 const dvt=async()=>{await page.goto(base+'/admin/#/domain');await btn('载入示例领域').click();await btn('理解 d=v×t · 新模型示例').click();return state();};
 return {page,base,btn,state,open,dvt,errors};
}
