import { chromium } from '@playwright/test';
import { readFile,writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const assets=new URL('../../design/assets/domain-model-v0.1/',import.meta.url);
const repo=new URL('../../../../../',import.meta.url);
const graphs=JSON.parse(await readFile(new URL('diagrams-input.json',assets),'utf8'));
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge'});
const page=await browser.newPage({viewport:{width:1500,height:1000}}),results=[];
try{
 await page.setContent('<html><body style="background:white;margin:20px"><main id="diagram"></main></body></html>');
 await page.addScriptTag({path:fileURLToPath(new URL('.tmp/mvp-diagram-review-20261011/tools/node_modules/mermaid/dist/mermaid.min.js',repo))});
 await page.evaluate(()=>mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral',fontFamily:'Microsoft YaHei, sans-serif',flowchart:{htmlLabels:false}}));
 for(const g of graphs){
  const svg=await page.evaluate(async g=>{const r=await mermaid.render(g.id,g.text);document.querySelector('#diagram').innerHTML=r.svg;return r.svg;},g);
  await writeFile(new URL(g.id+'.svg',assets),svg);
  await page.locator('#diagram svg').screenshot({path:fileURLToPath(new URL(g.id+'.png',assets))});
  results.push({id:g.id,document:g.document,index:g.index,sourceSha256:createHash('sha256').update(g.text).digest('hex')});
 }
}finally{await browser.close();}
await writeFile(new URL('diagram-render.json',assets),JSON.stringify({renderedAt:new Date().toISOString(),renderer:'local Mermaid and Edge',diagrams:results},null,2));
console.log(`Rendered ${results.length} diagrams`);
