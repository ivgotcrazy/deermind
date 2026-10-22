import type { AdminState, ModelObject } from './model';
import { seed } from './seed';

// Only known seed identities have an established mathematical meaning. Keep other
// legacy definitions discoverable without guessing their domain from their text.
export function migrateDomains(data: AdminState & { schema: number }): AdminState {
  const next = JSON.parse(JSON.stringify(data)) as AdminState;
  const baseline = seed();
  const known = new Set(baseline.objects.filter(o => o.domainId).map(o => o.id));
  next.schema = 3;
  next.domains = baseline.domains;
  let unclassified = false;
  function assign(o?: ModelObject) {
    if (!o || !['task', 'solution', 'kc'].includes(o.kind)) return;
    o.domainId = known.has(o.id) ? 'DOM-MATH' : 'DOM-LEGACY';
    if (o.domainId === 'DOM-LEGACY') unclassified = true;
  }
  next.objects.forEach(assign);
  next.issues.forEach(i => assign(i.candidate));
  if (unclassified) next.domains.push({
    id: 'DOM-LEGACY', name: '待归类的历史定义',
    scope: '升级前创建且尚无明确领域归属的对象。',
    description: '保留原定义与维护记录；此分组不代表已确定的学科或课程范围。',
    createdAt: new Date().toISOString(),
  });
  return next;
}

// Keep old issues read-only; unfinished definitions become editable local drafts.
// No approval or old workflow operation is invoked by the migration.
export function migrateDirectEditing(input: any): AdminState {
  const next: AdminState = input.schema===1 ? migrateDomains(input) : JSON.parse(JSON.stringify(input));
  next.schema=3; next.drafts=[]; next.changes=[]; next.annotations=[];
  for(const i of next.issues) {
    if(i.candidate && !i.published && i.dataMode==='demo') next.drafts.push({
      id:'legacy-'+i.id, object:JSON.parse(JSON.stringify(i.candidate)),
      baseVersion:i.proposedNew?0:i.baseVersion||0, sourceIssueId:i.id, at:i.candidate.at,
    });
  }
  return next;
}
