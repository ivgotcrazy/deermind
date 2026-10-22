import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { loadConfig } from './config.mjs';
import { createLiveApi } from './live-api.mjs';

const project = fileURLToPath(new URL('../', import.meta.url));
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.ico': 'image/x-icon', '.woff2': 'font/woff2' };

export function createPrototypeServer({ root = project, config, directory, provider, timeoutMs }) {
  const live = createLiveApi({ config, directory, provider, timeoutMs });
  return createServer(async (req, res) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Cache-Control', 'no-store');
    const port = req.socket.localPort;
    const hosts = [`127.0.0.1:${port}`, `localhost:${port}`];
    const reply = (code, body, type = 'text/plain; charset=utf-8') => {
      res.writeHead(code, { 'Content-Type': type });
      res.end(req.method === 'HEAD' ? undefined : body);
    };
    if (!hosts.includes(req.headers.host) ||
        (req.headers.origin && !hosts.some(host => req.headers.origin === `http://${host}`))) {
      reply(403, 'Local same-origin preview only.'); return;
    }
    try {
      const url = new URL(req.url || '/', 'http://localhost');
      if (await live(req, url, reply)) return;
      if (!['GET', 'HEAD'].includes(req.method)) { reply(405, 'Method not allowed.'); return; }
      if (url.pathname === '/__prototype_health') {
        reply(200, JSON.stringify({ name: 'deermind-mvp-prototype-next', pid: process.pid,
          root, stage: 'admin-workbench-review', pages: ['/student/', '/parent/', '/admin/'] }), 'application/json'); return;
      }
      if (url.pathname === '/' || /^\/(student|parent|admin)$/.test(url.pathname)) {
        res.writeHead(302, { Location: url.pathname === '/' ? '/student/' : `${url.pathname}/` });
        res.end(); return;
      }
      // Only serve each app's build output. No source files, .env or session files are reachable.
      const route = decodeURIComponent(url.pathname).match(/^\/(student|parent|admin)\/(.*)$/);
      if (!route) { reply(404, 'Not found.'); return; }
      const base = path.resolve(root, route[1], 'dist');
      // The unchanged legacy parent brand links to structure.html?role=parent.
      const entry = route[1] === 'parent' && route[2] === 'structure.html' ? 'index.html' : route[2];
      const file = path.resolve(base, entry || 'index.html');
      const relative = path.relative(base, file);
      if (relative.startsWith('..') || path.isAbsolute(relative)) { reply(403, 'Forbidden.'); return; }
      if (!(await stat(file)).isFile()) { reply(404, 'Not found.'); return; }
      reply(200, await readFile(file), mime[path.extname(file)] || 'application/octet-stream');
    } catch (error) {
      if (error instanceof URIError) reply(400, 'Invalid URL.');
      else if (['ENOENT', 'ENOTDIR'].includes(error.code)) reply(404, 'Not found.');
      else reply(500, 'Unable to read preview files.');
    }
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try {
    const args = process.argv.slice(2);
    const port = Number(args.includes('--port') ? args[args.indexOf('--port') + 1] : 5181);
    if (!Number.isInteger(port) || port < 1024 || port > 65535 || port === 5178) {
      throw new Error('Use a port from 1024 to 65535 other than the existing preview port 5178.');
    }
    const server = createPrototypeServer({ config: await loadConfig() });
    server.on('error', error => { console.error(error.message); process.exitCode = 1; });
    server.listen(port, '127.0.0.1', () => {
      console.log(`Student: http://127.0.0.1:${port}/student/`);
      console.log(`Parent: http://127.0.0.1:${port}/parent/`);
      console.log(`Admin: http://127.0.0.1:${port}/admin/`);
      console.log('V2 preview: live math-6b chat; page statistics remain demonstration data.');
    });
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
