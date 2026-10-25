import type { MaterialBlock, MaterialItem, MaterialRole } from '../../../shared/material-content';
import { emptyChapter, mockId, type MockTextbook } from './textbook-mock';

export const realBookPages=[49,50,91,92,93];
const block=(id:string,title:string,kind:MaterialBlock['kind'],role:MaterialRole,page:number,rect:MaterialBlock['rect'],text='',extra:Partial<MaterialBlock>={}):MaterialBlock=>({id,title,kind,role,page,rect,text,references:[],...extra});
const item=(id:string,title:string,kind:MaterialItem['kind'],blocks:MaterialBlock[],issue=''):MaterialItem=>({id,title,kind,blocks,reviewed:false,issue});
export function prepareRealBook(book:MockTextbook){
  const fraction=emptyChapter();fraction.name='分数的应用（一）';
  fraction.items=[
    item('MAT-GROUPS','三个兴趣小组的人数','例题',[
      block('B-CONDITIONS','情境与三个数量条件','image','condition',49,[5,22.2,90,28.2],'保留原情境图中的三个数量条件，不按画面中的人物个数推断人数。'),
      block('B-QUESTION','要求求出的量','text','question',49,[11,50.8,76,3.3],'航模小组有多少人？说一说你是如何思考的。'),
      block('B-HINT','教材中的引导问题','image','hint',49,[12,54.3,78,7.8]),
      block('B-DRAW-Q','画出数量关系','text','question',49,[12,62.3,77,2.6],'画图表示航模小组与气象小组、摄影小组人数之间的关系。'),
      block('B-DIAGRAM','数量关系的两种图示','image','figure',49,[16,65.4,36,25.6],'圆点图与线段图表达同一组数量关系。'),
      block('B-PROMPT','随图给出的思考提示','image','hint',49,[51,64.7,40,27.5]),
    ],'下一页的两种解法尚未归入本例题，请合并对应内容。'),
    item('MAT-METHODS','续页：两种解法','例题',[
      block('B-SOLVE-Q','列式解决问题','text','question',50,[8,3.8,50,2.4],'请列式解决问题。'),
      block('B-METHOD-A','先求中间量，再求最终量','image','solution',50,[6,7.2,41,20.4],'12 × 1/3 × 3/4 = 3（人）'),
      block('B-METHOD-B','先合并两层比例，再求人数','image','solution',50,[47.3,7.2,44.7,20.4],'12 × (1/3 × 3/4) = 3（人）'),
      block('B-ANSWER-BLANK','写出完整答语','image','blank',50,[10.5,30,35.5,4.2]),
      block('B-METHOD-HELP','理解另一种方法','image','hint',50,[57.2,28.8,23.5,8.2]),
    ]),
    item('MAT-MIXED','分数混合运算尝试','练习',[
      block('B-TRY','尝试计算','image','question',50,[12,44,78,8.5]),
      block('B-ORDER','运算顺序提示','image','hint',50,[33,52.8,49,9]),
    ]),
    item('MAT-ERROR','判断并解释计算错误','练习',[
      block('B-ERROR-Q','辨错要求','text','question',50,[8,65.1,79,2.4],'下面几道题算得对吗？计算时有什么好办法可以减少错误？'),
      block('B-ERROR-WORK','教材故意提供的待辨析算式','image','error',50,[18.7,69.4,58.5,12.7],'这些算式用于辨错，保留原样，不作为正确解法。'),
      block('B-ERROR-HINT','教材附带的检查提示','image','hint',50,[20,81.5,70.5,9.6]),
    ]),
  ];
  const research=emptyChapter();research.name='建设适老社会（一）';
  research.items=[
    item('MAT-PLAN','设计研究方案','探究活动',[
      block('B-PLAN-CONTEXT','研究背景','image','context',91,[10,24,84,19]),
      block('B-PLAN-Q','研究活动要求','text','question',91,[12,42.8,79,2.5],'怎样研究这个问题？小组讨论，形成研究方案。'),
      block('B-PLAN-HELP','讨论中的思考提示','image','hint',91,[8,45.5,86,7]),
      block('B-PLAN-BLANK','研究方案填写表','table','blank',91,[13.3,52.6,78.7,13.4],'这是学生待填写区域，不是识别漏字。',{headers:['收集什么样的数据','数据从哪里获取','怎样分析数据得出结论'],rows:[['','','']]}),
    ]),
    item('MAT-DATA','整理与比较人口数据','探究活动',[
      block('B-DATA-Q','收集与整理要求','text','question',91,[12,66,80,4.2],'按照小组设计的研究方案收集数据，并进行整理。'),
      block('B-DATA-HINT','两组数据的整理思路','image','hint',91,[12,69.6,81,6.8]),
      block('B-COUNTS','三次人口普查的老龄情况','table','data',91,[17,78.3,28.3,10.4],'',{unit:'人数：人',headers:['人口普查','60岁及以上人数','65岁以下人数'],rows:[['第五次','129977870','88274022'],['第六次','177648705','118831709'],['第七次','264018766','190635280']],issue:'第三列表头可能识别错误，请对照原表核对“以上 / 以下”。',resolved:false}),
      block('B-AGE','三次人口普查的年龄段占比','table','data',91,[47,79.2,45.2,12.7],'',{unit:'占比：%',headers:['人口普查','0～14岁','15～59岁','60～64岁','65岁及以上'],rows:[['第五次','22.89','66.78','3.37','6.96'],['第六次','16.60','70.14','4.37','8.87'],['第七次','17.95','63.35','5.20','13.50']]}),
      block('B-ANALYZE-Q','续页：观察与说明','text','question',92,[8,10,80,3],'观察整理后的数据，说一说我国人口老龄化的情况。',{references:['B-COUNTS','B-AGE']}),
      block('B-DATA-CONTINUE','续页：对数据的观察','image','hint',92,[11,13.4,81.5,18.6],'延续第 91 页的数据分析，不是另一组独立数据。',{references:['B-COUNTS','B-AGE']}),
    ]),
    item('MAT-LOCAL','调查本地区的人口老龄化情况','探究活动',[
      block('B-LOCAL-Q','设计、调查与交流','image','question',92,[8,40.6,82,12],'保留开放调查要求；此处没有预设数据或唯一答案，尚未提供在线调查工具。'),
    ]),
    item('MAT-AIR','空气质量是否改善','练习',[
      block('B-AIR-CONTEXT','空气质量背景材料','image','context',92,[9,53,82,16.8]),
      block('B-AIR-Q','观察年度空气质量数据','text','question',92,[10.5,69.7,80.5,5.8],'下面是淘气小组整理的 A 市2018—2020年空气质量等级情况。说一说，这个城市的空气质量明显改善了吗？'),
      block('B-AIR-TABLE','2018—2020 年空气质量情况','table','data',92,[20.5,76.6,52.1,10.6],'',{unit:'单位：天',headers:['年份','优','良','轻度污染','中度污染','重度污染','严重污染'],rows:[['2018','76','151','85','38','14','1'],['2019','85','159','88','29','4','0'],['2020','106','172','67','11','10','0']]}),
    ]),
  ];
  const charts=emptyChapter();charts.name='建设适老社会（二）';
  charts.items=[item('MAT-CHARTS','同一组数据的三种统计图','探究活动',[
    block('B-CHART-CHOICE','续接前课：选择统计图','text','question',92,[8,89.1,84,2.7],'想一想，用哪种统计图表示你们小组整理后的我国人口老龄化的数据？',{references:['B-COUNTS','B-AGE']}),
    block('B-CHART-Q','从统计图读取信息','text','question',93,[12,16.5,80,5.5],'同学们根据整理的我国人口老龄化的数据绘制成下面的统计图，从统计图中你能获得哪些信息？与同伴交流。'),
    block('B-BAR','老年人口数量条形统计图','image','data',93,[14,26,49.7,26.1],'图中人数以“亿”为单位，原始表格以“人”为单位；保留图例和舍入后的标注。',{references:['B-COUNTS']}),
    block('B-LINE','老年人口数量变化折线图','image','data',93,[14,54.6,49.5,27.3],'由同一人数表形成，重点呈现变化。',{references:['B-COUNTS']}),
    block('B-PIE','第七次人口普查年龄分布图','image','data',93,[64.1,38.8,28,36.4],'对应占比表的第七次普查行；图例颜色与年龄段一起保留。',{references:[],issue:'扇形图尚未关联到第 91 页的年龄占比表，请补上来源。',resolved:false}),
    block('B-CHART-HINT','教材对三类统计图的提示','image','hint',93,[5,82,92,9.4]),
  ])];
  book.units=[{id:mockId('UNIT'),name:'第四单元 分数的应用',chapters:[fraction]},{id:mockId('UNIT'),name:'第九单元 数据的表示和分析（三）',chapters:[research,charts]}];
  for(const ch of book.units.flatMap(u=>u.chapters)){
    const pages=[...new Set(ch.items!.flatMap(i=>i.blocks.map(b=>b.page)))];
    ch.locations=pages.map(page=>({id:mockId('LOC'),fileId:'BNU-PAGE-'+page,filePage:1,printedPage:String(page),label:'本课原页',text:'真实教材第 '+page+' 页，整理内容见图文项目。',image:'/admin/materials/bnu6a/page-'+page+'.png'}));
    ch.content=ch.items!.map(i=>i.title).join('\n');ch.reviewNote='图文整理候选尚待核对；原图真实，识别与关联均为 mock。';
  }
  return book;
}
