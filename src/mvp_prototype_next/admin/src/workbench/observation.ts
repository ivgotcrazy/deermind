import { objectKey, personalKinds, type AdminState, type ModelObject } from './model';

// Observation uses recorded versions, not the management catalog's latest-only view.
export function relatedActivities(s:AdminState, o:ModelObject, scope='') {
  return s.activities.filter(a=>(!scope || a.ls===scope) && a.objects.includes(objectKey(o)));
}
export function recordSpaces(s:AdminState, o:ModelObject) {
  return [...new Set([...relatedActivities(s,o).map(a=>a.ls), ...(o.fields.学习空间?[o.fields.学习空间]:[])])];
}
export function observedObjects(s:AdminState, space:string, scope='') {
  const bindings=scope?s.spaces.find(ls=>ls.id===scope)?.adopted:undefined;
  const versions=new Map<string,number>();
  for(const o of s.objects)if(o.status!=='draft')versions.set(o.id,Math.max(versions.get(o.id)||0,o.version));
  const recorded=new Set(s.activities.filter(a=>a.ls===scope).flatMap(a=>a.objects));
  return s.objects.filter(o=>{
    if(o.space!==space || o.status==='draft')return false;
    if(scope&&!bindings)return false;
    if(personalKinds.includes(o.kind))return !scope || recorded.has(objectKey(o)) || o.fields.学习空间===scope;
    if(scope)return bindings?.[o.id]===o.version;
    return versions.get(o.id)===o.version;
  });
}
export function observationStatus(s:AdminState,o:ModelObject) {
  return s.invalidated[objectKey(o)]?'已退出当前使用':personalKinds.includes(o.kind)?'已记录':'已保存定义';
}
