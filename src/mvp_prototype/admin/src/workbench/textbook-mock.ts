import { reactive } from 'vue';
import type { MaterialItem } from '../../../shared/material-content';

// Synthetic source excerpts and editable UI fixtures; no OCR or course adoption.
export interface MaterialSource { id:string; name:string; kind:string }
export interface SourceLocation { id:string; fileId:string; filePage:number; printedPage:string; label:string; text:string; image?:string }
export interface ChapterMapping { id:string; taskId:string; methods:string[]; sources:string[]; reason:string }
export interface MaterialChapter { id:string; name:string; content:string; locations:SourceLocation[]; mappings:ChapterMapping[]; checked:boolean; reviewNote:string; items?:MaterialItem[] }
export interface MaterialUnit { id:string; name:string; chapters:MaterialChapter[] }
export interface MockTextbook {
  id:string; name:string; publisher:string; edition:string; grade:string; subject:string; domainId:string; sourceNote:string;
  sources:MaterialSource[]; units:MaterialUnit[]; revision:number; history:{at:string;change:string}[];
}
export const mockId=(prefix:string)=>prefix+'-'+crypto.randomUUID().slice(0,8).toUpperCase();
export const emptyChapter=():MaterialChapter=>({id:mockId('CHAPTER'),name:'',content:'',locations:[],mappings:[],checked:false,reviewNote:''});
export const emptyTextbook=():MockTextbook=>({id:mockId('BOOK'),name:'',publisher:'',edition:'',grade:'',subject:'',domainId:'',sourceNote:'',sources:[],units:[],revision:1,history:[]});
const location=(id:string,filePage:number,printedPage:string,label:string,text:string):SourceLocation=>({id,fileId:'SOURCE-MATH',filePage,printedPage,label,text});
const mapping=(taskId:string,methods:string[],sources:string[],reason:string):ChapterMapping=>({id:'MAP-'+taskId,taskId,methods,sources,reason});
export const textbookMock=reactive({books:[{
  id:'BOOK-MATH',name:'小学数学·教材管理示例',publisher:'DeerMind 自编示例',edition:'交互演示版',grade:'小学高年级',subject:'数学',domainId:'DOM-MATH',sourceNote:'以下目录、页码和题目均为自编 mock，用于确认教材管理交互，不代表某本正式教材。',sources:[{id:'SOURCE-MATH',name:'数学学习材料（示例）.pdf',kind:'PDF'}],revision:1,history:[{at:'2026-10-24 09:00',change:'建立自编教材示例'}],
  units:[
    {id:'UNIT-FRACTIONS',name:'第一单元 分数的应用',chapters:[
      {id:'CH-PART',name:'求一个量的几分之几',content:'先明确分数对应的参照量，再根据比例求部分量。\n例：80 升水的四分之一是 20 升。',checked:true,reviewNote:'已对照示例页，确认参照量、数值和单位。',locations:[location('LOC-PART',6,'4','例 1','水箱中有 80 升水，用去其中的四分之一。用去了多少升？')],mappings:[mapping('part',['S0'],['LOC-PART'],'题目已知基准量和比例，所求为对应部分量。')]},
      {id:'CH-INCREASE',name:'按比例增加后的数量',content:'增加的比例以原量为参照。可以先求增加量再相加，也可以先求增加后的倍数。\n例 2：80 × 1/4 = 20，80 + 20 = 100（升）。\n练习 3：40 × (1 + 3/10) = 52（本）。',checked:false,reviewNote:'待核对示例的题面、方法范围和单位。',locations:[location('LOC-INCREASE-EX',8,'6','例 2','水箱原有 80 升水，又加入原有水量的四分之一。现在有多少升水？'),location('LOC-INCREASE-PRACTICE',9,'7','练习 3','班级原有 40 本图书，又购买了原有数量的十分之三。现在有多少本？')],mappings:[mapping('fraction',['S1-A'],['LOC-INCREASE-EX','LOC-INCREASE-PRACTICE'],'两处内容均求一次增加后的总量；本教材当前映射先采用“先求增加量，再求总量”。另一方法可在编辑中补充。')]},
    ]},
    {id:'UNIT-AREA',name:'第二单元 图形面积',chapters:[
      {id:'CH-TRIANGLE',name:'三角形的面积',content:'识别底与对应高，使用底 × 高 ÷ 2 求面积，并使用平方单位。\n例 1：12 × 7 ÷ 2 = 42（平方厘米）。',checked:true,reviewNote:'已核对底高对应关系及参考结果。',locations:[location('LOC-TRIANGLE',14,'12','例 1','三角形 ABC 的底 AB 长 12 厘米，C 到直线 AB 的垂直距离为 7 厘米。求三角形面积。')],mappings:[mapping('geometry',['S2-A'],['LOC-TRIANGLE'],'所求为三角形面积，底与对应高均已给定。')]},
      {id:'CH-GARDEN',name:'综合应用：扩建后的花园',content:'先求扩建后花坛的底长，再求三角形面积，最后求剩余面积。\n新底长为 10 米，花坛面积为 30 平方米，草坪面积为 210 平方米。',checked:false,reviewNote:'待核对区域包含关系。',locations:[location('LOC-GARDEN',18,'16','综合练习 2','长方形花园长 20 米、宽 12 米。角落的直角三角形花坛两直角边沿花园相邻边，其中一条原长 8 米，增加原长的四分之一，另一条保持 6 米。其余区域铺草坪，求草坪面积。')],mappings:[mapping('composite',['S3-A'],['LOC-GARDEN'],'覆盖尺寸推导、花坛面积及区域相减的完整任务；不能只根据三角形面积 KC 判断覆盖。')]},
    ]},
    {id:'UNIT-NEXT',name:'第三单元 待整理内容',chapters:[{...emptyChapter(),id:'CH-PENDING',name:'比例关系'}]},
  ],
}] as MockTextbook[]});
export const textbookNavigation=reactive<Record<string,{query:string;expanded:string[]}>>({});
export function recordBookChange(book:MockTextbook,change:string){book.revision++;book.history.unshift({at:new Date().toLocaleString('sv-SE',{hour12:false}),change});}
