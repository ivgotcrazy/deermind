import type { components } from '../../../../../contracts/generated/http/schema';
import { readMember, type DomainSession } from '../domain/api';

type Method = components['schemas']['SolutionRef'];

export function methodKey(method: Method) {
  return `${method.object_id}:${method.version}`;
}

export async function methodNames(
  session: DomainSession,
  domain: string,
  methods: Method[],
): Promise<Record<string, string>> {
  const refs = new Map(methods.map((method) => [methodKey(method), method]));
  const results = await Promise.allSettled(
    Array.from(refs, async ([key, method]) => {
      const result = await readMember(
        domain,
        method.object_id,
        'solution',
        session,
        new AbortController().signal,
        method.version,
      );
      return [key, result.content.name] as const;
    }),
  );
  return Object.fromEntries(
    results.flatMap((result) => (result.status === 'fulfilled' ? [result.value] : [])),
  );
}
