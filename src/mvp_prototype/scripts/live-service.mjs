import { mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { systemPrompt, validateOutput } from './live-model.mjs';

export class LiveError extends Error { constructor(message, status = 400) { super(message); this.status = status; } }
const now = () => new Date().toISOString();
const idPattern = /^[a-zA-Z0-9-]{8,80}$/;
export function createLiveService({ directory, provider, model, reference = '', timeoutMs = 90000, configured = true }) {
  const cache = new Map(), loading = new Map(), queues = new Map(), controllers = new Map();
  async function save(s) {
    await mkdir(directory, { recursive: true });
    const file = path.join(directory, `${s.id}.json`), temp = `${file}.tmp`;
    await writeFile(temp, JSON.stringify(s, null, 2), 'utf8'); await rename(temp, file);
  }
  async function load(id) {
    if (!idPattern.test(id)) throw new LiveError('对话编号无效。');
    if (cache.has(id)) return cache.get(id);
    if (!loading.has(id)) loading.set(id, (async () => {
      let s;
      try { s = JSON.parse(await readFile(path.join(directory, `${id}.json`), 'utf8')); }
      catch { throw new LiveError('未找到这次真实对话。请检查是否在原电脑、原项目中启动服务。', 404); }
      if (s.pending) { s.error = { message: '服务曾中断，上一轮没有取得可用回复，可重试。', retryable: true }; s.pending = null; await save(s); }
      cache.set(id, s); return s;
    })().finally(() => loading.delete(id)));
    return loading.get(id);
  }
  function exclusive(id, fn) {
    const next = (queues.get(id) || Promise.resolve()).then(fn);
    queues.set(id, next.catch(() => {})); return next;
  }
  function publicView(s) {
    const { lastCommand, requests, ...view } = s;
    return { ...view, turns: s.turns.map(t => {
      if (t.role !== 'assistant') return t;
      const { raw, ...turn } = t;
      return { ...turn, blocks: t.blocks.map(({ referenceAnswer, ...b }) => b) };
    }) };
  }
  const question = (s, id) => s.turns.flatMap(t => t.blocks || []).find(b => b.type === 'question' && b.id === id);
  function messages(s) {
    const history = s.turns.map(t => ({ role: t.role, content: t.role === 'assistant' ? JSON.stringify({ blocks: t.blocks.map(({ id, state, answer, ...b }) => b), suggestions: t.suggestions }) : t.text }));
    return [{ role: 'system', content: systemPrompt(reference) }, ...history];
  }
  async function run(s, token, controller) {
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    timeout.unref?.();
    const calls = [], started = Date.now();
    try {
      const context = messages(s);
      let output;
      for (let attempt = 0; attempt < 2; attempt++) {
        const result = await provider(context, controller.signal);
        calls.push({ ms: result.ms, usage: result.usage, finish: result.finish });
        try {
          if (result.finish === 'length') throw Error('truncated');
          output = validateOutput(JSON.parse(result.raw));
          if (s.lastCommand.kind === 'check_request' && !output.blocks.some(b => b.type === 'question' && b.mode === 'check')) throw Error('missing check');
          if (s.lastCommand.kind === 'practice_request' && !output.blocks.some(b => b.type === 'question' && b.mode === 'practice')) throw Error('missing practice');
          break;
        } catch {
          if (attempt === 1) throw new LiveError('模型未返回可用的内容格式，未展示不完整回复。可重试本轮。', 502);
          context.push({ role: 'assistant', content: result.raw.slice(0, 24000) }, { role: 'user', content: '刚才输出不符合约定 JSON 结构或本轮所需 question 模式。请重发完整合法 JSON，保持本轮请求，不添加学生表现。' });
        }
      }
      await exclusive(s.id, async () => {
        if (controllers.get(s.id) !== controller || s.pending?.id !== token) return;
        for (const b of output.blocks) if (b.type === 'question') { b.id = randomUUID(); b.state = 'offered'; }
        s.turns.push({ id: randomUUID(), role: 'assistant', ...output, at: now(), metrics: { ms: Date.now() - started, calls } });
        s.pending = null; s.error = null; s.updatedAt = now(); await save(s);
      });
    } catch (e) {
      await exclusive(s.id, async () => {
        if (controllers.get(s.id) !== controller || s.pending?.id !== token) return;
        const message = controller.signal.aborted ? '模型等待超时，输入已保留。可稍后重试。' : e instanceof LiveError || /API Key|模型账户|模型服务/.test(e.message) ? e.message : '未能连接模型服务，输入已保留。请检查网络后重试。';
        s.error = { message, retryable: true, calls, ms: Date.now() - started }; s.pending = null; s.updatedAt = now(); await save(s);
      });
    } finally { clearTimeout(timeout); if (controllers.get(s.id) === controller) controllers.delete(s.id); }
  }
  async function command(id, command) {
    return exclusive(id, async () => {
      const s = structuredClone(await load(id));
      if (!idPattern.test(command.requestId || '')) throw new LiveError('请求编号无效。');
      const fingerprint = JSON.stringify(command);
      if (s.requests[command.requestId]) {
        if (s.requests[command.requestId] !== fingerprint) throw new LiveError('同一请求编号不能提交不同内容。', 409);
        return publicView(s);
      }
      if (command.kind === 'cancel') {
        controllers.get(id)?.abort(); controllers.delete(id);
        if (s.pending) { s.pending = null; s.error = { message: '已停止生成。输入保留，可重试或直接提出新的问题。', retryable: true }; }
      } else {
        if (s.pending) throw new LiveError('上一轮仍在处理，请等待或停止生成。', 409);
        if (command.kind === 'end') {
          if (s.check) { question(s, s.check).state = 'skipped'; s.check = null; }
          s.phase = 'ended'; s.error = null; s.turns.push({ id: randomUUID(), role: 'user', text: '这次先到这里。', at: now(), action: 'end' });
        } else if (command.kind === 'resume') {
          s.phase = 'learning'; s.error = null; s.turns.push({ id: randomUUID(), role: 'user', text: '继续上次的交流。', at: now(), action: 'resume' });
        } else if (command.kind === 'start_check') {
          if (s.phase === 'ended' || s.check) throw new LiveError('当前不能开始另一道检查。');
          const q = question(s, command.questionId);
          if (!q || q.mode !== 'check' || q.state !== 'offered') throw new LiveError('这道检查已经处理或不存在。');
          q.state = 'active'; s.check = q.id; s.phase = 'check'; s.error = null;
        } else {
          if (!configured) throw new LiveError('请在项目根目录 .env 配置 DEERMIND_LLM_API_KEY 后重启。', 503);
          if (s.phase === 'ended') throw new LiveError('这次对话已暂停，请先继续。');
          const allowed = ['message', 'practice_request', 'check_request', 'answer', 'help', 'retry'];
          if (!allowed.includes(command.kind)) throw new LiveError('不支持的操作。');
          if (s.check && !['answer', 'help'].includes(command.kind)) throw new LiveError('请提交当前答案，或结束检查后求助。');
          if (command.kind === 'retry') {
            if (!s.error?.retryable || !s.lastCommand) throw new LiveError('没有需要重试的回复。');
          } else {
            if (s.turns.length >= 160) throw new LiveError('本次对话已达到 160 条记录，请另开对话继续。');
            let text = typeof command.text === 'string' ? command.text.trim() : '';
            if (text.length > 12000) throw new LiveError('本次输入过长，请分段发送（每次最多 12000 字符）。');
            if (command.kind === 'message' && !text) throw new LiveError('请先输入想讨论的内容。');
            if (command.kind === 'practice_request') text = '请根据刚才交流准备一道合适的新练习，question mode=practice，先不要给答案。';
            if (command.kind === 'check_request') text = '请根据刚才交流准备一道未展示过的新题，检查这次是否理解。question mode=check，先不要给提示或答案。';
            if (command.kind === 'answer') {
              const q = question(s, command.questionId);
              if (!q || !['offered', 'active'].includes(q.state) || (q.mode === 'check' && s.check !== q.id) || (s.check && s.check !== q.id) || !text) throw new LiveError('请先开始这道检查或填写可提交的答案。');
              q.answer = text; q.state = 'answered'; s.check = null; s.phase = 'learning';
              text = `我对这道${q.mode === 'check' ? '即时检查' : '练习'}提交的原文：${text}\n题目：${q.prompt}\n本次提交已结束该题作答，请根据实际表达反馈；若原文是在求助，不要当成有效答案，直接讲解。`;
            }
            if (command.kind === 'help') {
              if (!s.check) throw new LiveError('当前没有正在进行的检查。');
              const q = question(s, s.check); q.state = 'helped'; s.check = null; s.phase = 'learning';
              text = `我请求帮助，结束这道检查，尚未提交答案。题目：${q.prompt}\n${text || '请讲讲我应该怎样理解这道题。'}`;
            }
            // Only genuine inputs and deterministic activity events enter history.
            if (command.kind !== 'answer') for (const q of s.turns.flatMap(t => t.blocks || [])) if (q.type === 'question' && q.state === 'offered' && ['practice_request', 'check_request'].includes(command.kind)) q.state = 'skipped';
            const label = { practice_request: '出一道练习，先让我试试。', check_request: '检查一下这次是否理解了。', help: '请帮我讲讲这道题。' }[command.kind];
            s.turns.push({ id: randomUUID(), role: 'user', text, displayText: command.text?.trim() || label || text, action: command.kind, at: now() });
            s.lastCommand = { kind: command.kind };
          }
          if (JSON.stringify(messages(s)).length > 180000) throw new LiveError('本次交流较长，请另开对话；已有内容保留。');
          s.error = null; s.pending = { id: command.requestId, startedAt: now() };
        }
      }
      s.requests[command.requestId] = fingerprint; s.updatedAt = now(); await save(s); cache.set(id, s);
      if (s.pending && !controllers.has(id)) {
        const controller = new AbortController(); controllers.set(id, controller);
        void run(s, s.pending.id, controller).catch(() => { /* Disk failure remains pending for explicit recovery after restart. */ });
      }
      return publicView(s);
    });
  }
  return {
    async create() {
      const s = { version: 1, id: `REAL-${randomUUID()}`, model, chapter: 'fractions', phase: 'learning', check: null, turns: [], pending: null, error: null, lastCommand: null, requests: {}, createdAt: now(), updatedAt: now() };
      await save(s); cache.set(s.id, s); return publicView(s);
    },
    async get(id) { return publicView(await load(id)); }, command,
  };
}
