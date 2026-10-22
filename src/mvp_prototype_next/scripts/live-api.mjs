import { fileURLToPath } from 'node:url';
import { createLiveService, LiveError } from './live-service.mjs';
import { createProvider } from './live-model.mjs';

// Curriculum context only. This is the V2 preview scope, not a published Domain package.
export const previewScope = Object.freeze({ space: 'math-6b', label: '六年级下册数学',
  topics: ['负数', '百分数（二）', '圆柱与圆锥', '比例', '鸽巢问题', '整理和复习'],
  source: 'V2 原型课程目录；未接入正式教材映射或个人能力评价',
  checkConditions: '上文和右侧页面始终可见，不据此认定独立作答' });

export function createLiveApi({ config, directory = fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/sessions/', import.meta.url)), provider, timeoutMs }) {
  const service = createLiveService({ directory, provider: provider || createProvider(config),
    model: config.model, configured: !!config.key, timeoutMs });
  async function body(req) {
    if (!req.headers['content-type']?.startsWith('application/json')) throw new LiveError('需要 JSON 请求。', 415);
    let size = 0; const chunks = [];
    for await (const chunk of req) {
      size += chunk.length;
      if (size > 100000) throw new LiveError('请求过大。', 413);
      chunks.push(chunk);
    }
    try { const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
      if (!value || Array.isArray(value) || typeof value !== 'object') throw Error();
      return value;
    } catch { throw new LiveError('请求不是有效 JSON。'); }
  }
  return async (req, url, reply) => {
    if (!url.pathname.startsWith('/api/live/')) return false;
    const json = (status, value) => reply(status, JSON.stringify(value), 'application/json; charset=utf-8');
    try {
      if (url.pathname === '/api/live/admin/sessions' && req.method === 'GET') {
        json(200, await service.inspectIndex(previewScope.space));
      } else if (url.pathname.startsWith('/api/live/admin/sessions/') && req.method === 'GET') {
        const match=url.pathname.match(/^\/api\/live\/admin\/sessions\/(NEXT-[a-zA-Z0-9-]+)$/);
        if(!match) throw new LiveError('会话编号无效。');
        const current=await service.inspect(match[1]);
        if(current.scope.space !== previewScope.space) throw new LiveError('会话不属于当前课程。',409);
        json(200,current);
      } else if (url.pathname === '/api/live/status' && req.method === 'GET') {
        json(200, { configured: !!config.key, model: config.model, connected: true, space: previewScope.space });
      } else if (url.pathname === '/api/live/sessions' && req.method === 'POST') {
        const data = await body(req);
        if (data.space !== previewScope.space) throw new LiveError('当前仅接入六年级下册数学。');
        if (typeof data.creationId !== 'string') throw new LiveError('缺少创建请求编号。');
        json(200, await service.create(previewScope, data.creationId));
      } else {
        const match = url.pathname.match(/^\/api\/live\/sessions\/(NEXT-[a-zA-Z0-9-]+)(\/commands)?$/);
        if (!match) { json(404, {error:'接口不存在。'}); return true; }
        const current = await service.get(match[1]);
        if (current.scope.space !== previewScope.space) throw new LiveError('会话不属于当前课程。', 409);
        if (!match[2] && req.method === 'GET') json(200, current);
        else if (match[2] && req.method === 'POST') json(200, await service.command(match[1], await body(req)));
        else json(405, {error:'不支持此请求方法。'});
      }
    } catch (e) { json(e instanceof LiveError ? e.status : 500,
      {error: e instanceof LiveError ? e.message : '会话读写失败，输入应保留。请检查服务后重试。'}); }
    return true;
  };
}
