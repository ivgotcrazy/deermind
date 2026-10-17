import { fileURLToPath } from 'node:url';
import { loadConfig, loadReference, createProvider } from './live-model.mjs';
import { createLiveService, LiveError } from './live-service.mjs';

const root = new URL('../../../', import.meta.url);
const config = await loadConfig(root);
const service = createLiveService({ directory: fileURLToPath(new URL('.tmp/mvp-live/', root)), provider: createProvider(config), model: config.model, configured: !!config.key, reference: await loadReference(root) });
export async function handleLive(req, res, port) {
  const url = new URL(req.url || '/', 'http://localhost');
  if (!url.pathname.startsWith('/api/live/')) return false;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  const send = (status, value) => { res.writeHead(status); res.end(JSON.stringify(value)); };
  try {
    const hosts = [`127.0.0.1:${port}`, `localhost:${port}`];
    if (!['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.socket.remoteAddress) || !hosts.includes(req.headers.host) || (req.headers.origin && !hosts.some(h => req.headers.origin === `http://${h}`))) throw new LiveError('真实模型对话仅开放给本机同源页面。', 403);
    if (req.method === 'GET' && url.pathname === '/api/live/status') { send(200, { configured: !!config.key, model: config.model, scope: '分数的应用' }); return true; }
    const match = url.pathname.match(/^\/api\/live\/sessions\/([a-zA-Z0-9-]{8,80})(\/commands)?$/);
    if (req.method === 'GET' && match && !match[2]) { send(200, await service.get(match[1])); return true; }
    if (req.method !== 'POST' || req.headers['x-deermind-live'] !== '1' || !req.headers['content-type']?.startsWith('application/json')) throw new LiveError('请求方式不受支持。', 405);
    const chunks = []; let size = 0;
    for await (const part of req) { size += part.length; if (size > 128000) throw new LiveError('请求内容过长。', 413); chunks.push(part); }
    const raw = Buffer.concat(chunks).toString('utf8');
    let body; try { body = JSON.parse(raw); } catch { throw new LiveError('请求不是有效 JSON。'); }
    if (url.pathname === '/api/live/sessions') send(201, await service.create());
    else if (match?.[2]) send(200, await service.command(match[1], body));
    else throw new LiveError('没有此接口。', 404);
  } catch (e) { send(e instanceof LiveError ? e.status : 500, { error: e instanceof LiveError ? e.message : '本地服务暂时无法保存或读取，请查看服务状态后重试。' }); }
  return true;
}
