import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const args = process.argv.slice(2);
const port = Number(args.includes('--port') ? args[args.indexOf('--port') + 1] : 5178);
const host = args.includes('--host') ? args[args.indexOf('--host') + 1] : '127.0.0.1';
if (
  !Number.isInteger(port) ||
  port < 1024 ||
  port > 65535 ||
  !['127.0.0.1', '0.0.0.0'].includes(host)
)
  throw new Error('Invalid host or port');
const root = fileURLToPath(new URL('../dist/', import.meta.url));
const mime = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};
const server = createServer(async (req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405).end();
    return;
  }
  try {
    const url = new URL(req.url || '/', 'http://localhost');
    if (url.pathname === '/__prototype_health') {
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ name: 'deermind-mvp-prototype', pid: process.pid }));
      return;
    }
    const name = decodeURIComponent(url.pathname).replace(/^\/+/, '') || 'index.html';
    const file = path.resolve(root, name);
    const relative = path.relative(root, file);
    if (relative.startsWith('..') || path.isAbsolute(relative)) {
      res.writeHead(403).end();
      return;
    }
    if (!(await stat(file)).isFile()) {
      res.writeHead(404).end();
      return;
    }
    res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream');
    res.end(req.method === 'HEAD' ? undefined : await readFile(file));
  } catch {
    res.writeHead(404).end('Not found');
  }
});
server.on('error', (error) => {
  console.error(error.message);
  process.exit(1);
});
server.listen(port, host, () => console.log(`DeerMind prototype: http://${host}:${port}`));
