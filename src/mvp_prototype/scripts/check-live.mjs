// Explicit paid smoke check. Normal npm test never calls the model.
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
if (!process.argv.includes('--run')) { console.log('Use node scripts/check-live.mjs --run to make six real model turns against the running local prototype.'); process.exit(0); }
const base = 'http://127.0.0.1:5178';
const dir = fileURLToPath(new URL('../../../.tmp/mvp-live-check/', import.meta.url));
await mkdir(dir, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
page.setDefaultTimeout(15000);
let sessionId;
const errors=[];page.on('pageerror',e=>errors.push(e.message));
async function snapshot(){return (await page.request.get(`${base}/api/live/sessions/${sessionId}`)).json();}
async function waitReply(count){
 const deadline=Date.now()+110000;
 while(Date.now()<deadline){const s=await snapshot();if(!s.pending&&s.turns.filter(t=>t.role==='assistant').length>=count){await page.waitForFunction(n=>document.querySelectorAll('.live-turn.assistant').length>=n,count);console.log(JSON.stringify({turn:count,ms:s.turns.at(-1).metrics?.ms,blocks:s.turns.at(-1).blocks?.map(b=>b.type)}));return s;}if(s.error)throw Error(s.error.message);await new Promise(r=>setTimeout(r,750));}
 throw Error('Model smoke check timed out.');
}
try {
 await page.goto(`${base}/structure.html?role=student#/chapter?chapter=fractions`);
 await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();
 await page.getByLabel('向真实 DeerMind 提问').waitFor();sessionId=new URL(page.url().split('#')[1],'http://local').searchParams.get('id');
 await page.getByRole('button',{name:'为什么要除以比较的标准量？'}).click();await waitReply(1);
 await page.getByLabel('向真实 DeerMind 提问').fill('换一种方法，用条形图解释为什么比较的标准改变，分母也会改变，先不要出题。');await page.getByRole('button',{name:'发送',exact:true}).click();await waitReply(2);
 await page.getByRole('button',{name:'出一道练习',exact:true}).click();await waitReply(3);
 await page.getByLabel('练习答案',{exact:true}).last().fill('我认为分母始终应该用较大的量，因为大数在下面比较好算。');await page.getByRole('button',{name:'提交这道练习',exact:true}).last().click();await waitReply(4);
 await page.getByRole('button',{name:'检查这次理解',exact:true}).click();await waitReply(5);
 await page.getByRole('button',{name:'开始这道检查',exact:true}).last().click();
 await page.getByLabel('检查答案',{exact:true}).fill('我不知道这次要和谁比较。');
 await page.reload();await page.getByLabel('检查答案',{exact:true}).waitFor();
 if(await page.getByLabel('检查答案',{exact:true}).inputValue()!=='我不知道这次要和谁比较。')throw Error('Draft was lost.');
 if(await page.locator('.live-turn').count()!==1)throw Error('Teaching leaked into active check view.');
 await page.screenshot({path:`${dir}/active-check.png`});
 await page.getByRole('button',{name:'求助并结束检查',exact:true}).click();await waitReply(6);
 await page.getByLabel('向真实 DeerMind 提问').waitFor();
 await page.locator('.live-scroll').evaluate(e=>e.scrollTop=e.scrollHeight);await page.screenshot({path:`${dir}/desktop.png`});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${dir}/narrow.png`});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow.');
 await page.getByRole('button',{name:'这次先到这里',exact:true}).click();await page.getByRole('heading',{name:'这次交流已保存'}).waitFor();await page.reload();await page.getByRole('button',{name:'继续这次交流',exact:true}).click();await page.getByLabel('向真实 DeerMind 提问').waitFor();
 const s=await snapshot();
 if(errors.length)throw Error(errors.join('\n'));
 await writeFile(`${dir}/result.json`,JSON.stringify({checkedAt:new Date().toISOString(),sessionId,errors,session:s},null,2),'utf8');
 console.log(JSON.stringify({result:'PASS',sessionId,turns:s.turns.filter(t=>t.role==='assistant').length,saved:dir}));
}catch(e){await page.screenshot({path:`${dir}/failure.png`});console.error(e.message);process.exitCode=1;}
finally{await browser.close();}
