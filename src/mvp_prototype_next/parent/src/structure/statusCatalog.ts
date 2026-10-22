import { chapters } from './data';

export type StatusChapter = {
  id: string; name: string; order: string; book: string; unit: string;
  reference: boolean; requirements: string[];
};

// Presentation stress fixtures only. Added rows have no learner judgments or teaching content.
// They never enter the Domain model, real conversations, or the parent's course data.
export function statusCatalog(scale: number): StatusChapter[] {
  const source: StatusChapter[] = chapters.map(c => ({
    id:c.id, name:c.name, order:c.order, book:'六年级上册', unit:'',
    reference:true, requirements:c.requirements,
  }));
  const size = [30,300].includes(scale) ? scale : 3;
  for(let i=0; i<size-3; i++) {
    source.push({
      id:`catalog-${i+1}`, book:`示例分册 ${Math.floor(i/100)+1}`,
      unit:`单元 ${String(Math.floor((i%100)/10)+1).padStart(2,'0')}`,
      order:`第 ${i%10+1} 节`,
      name:i%10===0?'综合应用':i%10===1?'从多种表示方式理解数量关系，并解释不同条件下解决问题的方法与适用范围':`数量关系与应用 ${i%10+1}`,
      reference:false, requirements:[],
    });
  }
  return source;
}

export const chapterPath = (c: StatusChapter) => [c.book,c.unit,c.order].filter(Boolean).join(' / ');
