/** 类型来自后端OpenAPI；不自动重发写请求，不在这里推断业务是否完成。 */
import type { components, paths } from '../../../../contracts/generated/http/schema';

type Method = 'get' | 'post' | 'put';
type Route<M extends Method> = {
  [P in keyof paths]: paths[P][M] extends { responses: object } ? P : never;
}[keyof paths];
type Success<O> = O extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;
type Accepted<O> = O extends { responses: { 202: { content: { 'application/json': infer R } } } }
  ? R
  : never;
type Body<O> = O extends { requestBody: { content: { 'application/json': infer B } } }
  ? B
  : undefined;
type Query<O> = O extends { parameters: { query?: infer Q } } ? Q : never;
type Params<O> = O extends { parameters: { path: infer P } } ? P : never;
type Session = Pick<components['schemas']['SessionView'], 'session_id' | 'csrf_token'>;
type Options = { session?: Session; signal?: AbortSignal };

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

async function send<T>(
  path: string,
  method: Method,
  options: Options,
  body?: unknown,
  expectedStatus = 200,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.session) {
    headers['X-Expected-Session'] = options.session.session_id;
    if (method !== 'get') headers['X-CSRF-Token'] = options.session.csrf_token;
  }
  if (body !== undefined)
    headers['Content-Type'] = body instanceof File ? body.type : 'application/json';
  const response = await fetch(path, {
    method: method.toUpperCase(),
    credentials: 'same-origin',
    cache: 'no-store',
    headers,
    signal: options.signal,
    body: body instanceof File ? body : body === undefined ? undefined : JSON.stringify(body),
  });
  const value: unknown = await response.json();
  if (!response.ok) {
    const detail = value && typeof value === 'object' && 'error' in value ? value.error : null;
    if (
      detail &&
      typeof detail === 'object' &&
      'code' in detail &&
      typeof detail.code === 'string' &&
      'message' in detail &&
      typeof detail.message === 'string'
    ) {
      throw new ApiError(response.status, detail.code, detail.message);
    }
    throw new Error('服务返回的错误格式不正确，请先查询原请求结果。');
  }
  if (response.status !== expectedStatus) throw new Error('收到未声明的响应，请先查询原请求结果。');
  return value as T;
}

export function putFile<P extends Route<'put'>>(
  path: P,
  file: File,
  options: Options & { params: Params<paths[P]['put']> },
): Promise<Success<paths[P]['put']>> {
  return send(resolvePath(path, options.params), 'put', options, file);
}

function resolvePath(path: string, values?: object): string {
  const params = new Map(Object.entries(values ?? {}));
  return path.replace(/\{([^}]+)\}/g, (_placeholder, name: string) => {
    const value = params.get(name);
    if (value === undefined) throw new Error(`请求缺少路径参数 ${name}。`);
    return encodeURIComponent(String(value));
  });
}

export function get<P extends Route<'get'>>(
  path: P,
  options: Options & { query?: Query<paths[P]['get']>; params?: Params<paths[P]['get']> } = {},
): Promise<Success<paths[P]['get']>> {
  const resolved = resolvePath(path, options.params);
  const query = new URLSearchParams();
  if (options.query)
    for (const [key, value] of Object.entries(options.query)) {
      if (Array.isArray(value)) {
        for (const item of value) query.append(key, String(item));
      } else if (value !== undefined) {
        query.set(key, String(value));
      }
    }
  return send(resolved + (query.size ? `?${query}` : ''), 'get', options);
}

export function post<P extends Route<'post'>>(
  path: P,
  body: Body<paths[P]['post']>,
  options: Options & { params?: Params<paths[P]['post']> } = {},
): Promise<Success<paths[P]['post']>> {
  return send(resolvePath(path, options.params), 'post', options, body);
}

export function postAccepted<P extends Route<'post'>>(
  path: P,
  body: Body<paths[P]['post']>,
  options: Options & { params?: Params<paths[P]['post']> } = {},
): Promise<Accepted<paths[P]['post']>> {
  return send(resolvePath(path, options.params), 'post', options, body, 202);
}
