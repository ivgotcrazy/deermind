export interface ContentVisual {
  id:string; title:string; kind:'relation'|'table'|'description'; description:string;
  origin:'教材提取'|'系统生成'|'人工整理'|'来源待确认'; sourceNote:string;
  nodes?:string[]; links?:string[]; table?:{headers:string[];rows:string[][]};
}
export function visualIssues(visuals:ContentVisual[]=[]):string[]{
  return visuals.flatMap(v=>{
    const issues:string[]=[];
    if(!v.title.trim()||!v.description.trim()||!v.sourceNote.trim())issues.push('补齐图表名称、含义与来源');
    if(v.origin==='来源待确认')issues.push('核对图表来源');
    if(v.kind==='relation'&&(!v.nodes||v.nodes.length<2||v.nodes.some(n=>!n.trim())||v.links?.length!==v.nodes.length-1))issues.push('核对关系图的对象与连接');
    if(v.kind==='table'&&(!v.table?.headers.length||v.table.headers.some(h=>!h.trim())||!v.table.rows.length||v.table.rows.some(r=>r.length!==v.table!.headers.length)))issues.push('核对图表行列结构');
    return issues.map(i=>v.title+'：'+i);
  });
}
