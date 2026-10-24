// Teaching-material interaction fixtures, not OCR output or learner evidence.
export type MaterialRole = 'context'|'condition'|'question'|'figure'|'hint'|'solution'|'error'|'blank'|'data';
export const materialRoles:Record<MaterialRole,string>={context:'背景说明',condition:'题目条件',question:'问题 / 要求',figure:'关系图示',hint:'思考提示',solution:'解法示例',error:'辨错材料',blank:'学生待完成',data:'已给数据'};
export interface MaterialBlock {
  id:string; title:string; kind:'text'|'formula'|'image'|'table'; role:MaterialRole;
  page:number; rect:[number,number,number,number]; text:string;
  headers?:string[]; rows?:string[][]; unit?:string;
  references:string[]; issue?:string; resolved?:boolean;
}
export interface MaterialItem {
  id:string; title:string; kind:'例题'|'练习'|'探究活动'|'阅读';
  blocks:MaterialBlock[]; reviewed:boolean; issue?:string;
}
export const materialPageUrl=(page:number)=>'/admin/materials/bnu6a/page-'+page+'.png';
export const publisherBookUrl='https://www.100875.com.cn/show/eBookAndTeacher.html?resId=7965194976af40f5b9abc4b3f89522fe&bookId=120170718181616016000&firstNum=120170718181616016000&contributeId=9276';
export function visibleMaterialBlocks(item:MaterialItem,mode:'all'|'question'){
  return item.blocks.filter(b=>mode==='all'||['context','condition','question','error','blank','data'].includes(b.role));
}
export const materialProblems=(items:MaterialItem[])=>items.flatMap(i=>[...(i.issue?[i.issue]:[]),...i.blocks.filter(b=>b.issue&&!b.resolved).map(b=>b.issue!)]);
