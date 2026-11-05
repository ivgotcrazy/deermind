import { chromium } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const assets=new URL('../../design/assets/domain-material-v0.1/',import.meta.url);
const repo=new URL('../../../../../',import.meta.url);
const mermaid=new URL('.tmp/mvp-diagram-review-20261011/tools/node_modules/mermaid/dist/mermaid.min.js',repo);
const prd=await readFile(new URL('../../PRD.md',import.meta.url),'utf8');
const diagrams=[{id:'model-relations',text:await readFile(new URL('model-relations.mmd',assets),'utf8')},...Array.from(prd.matchAll(/```mermaid\n([\s\S]*?)```/g),(m,i)=>({id:'prd-'+(i+1),text:m[1]}))];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1500,height:1100},deviceScaleFactor:1});
const results=[];
try {
  await page.setContent('<html><body style="margin:16px;background:white"><div id="diagram"></div></body></html>');
  await page.addScriptTag({path:fileURLToPath(mermaid)});
  await page.evaluate(()=>mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral',fontFamily:'Microsoft YaHei, sans-serif',flowchart:{htmlLabels:false,useMaxWidth:true}}));
  for(const d of diagrams){
    const svg=await page.evaluate(async({id,text})=>{const result=await mermaid.render(id,text);document.querySelector('#diagram').innerHTML=result.svg;return result.svg;},d);
    await writeFile(new URL(d.id+'.svg',assets),svg);
    await page.locator('#diagram svg').screenshot({path:fileURLToPath(new URL(d.id+'.png',assets))});
    results.push({id:d.id,sourceSha256:createHash('sha256').update(d.text).digest('hex'),svg:d.id+'.svg',png:d.id+'.png'});
  }
} finally {await browser.close();}
await writeFile(new URL('diagram-render.json',assets),JSON.stringify({renderedAt:new Date().toISOString(),renderer:'local Mermaid 11.12.0 + Chromium',diagrams:results},null,2));
console.log('Rendered '+results.length+' diagrams');
