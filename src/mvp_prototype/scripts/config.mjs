import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

export const repository = new URL('../../../', import.meta.url);
export const sessionDirectory = fileURLToPath(new URL('.tmp/mvp-live/', repository));

// Preserve the existing configuration contract; never copy credentials into a frontend build.
export async function loadConfig(root = repository, environment = process.env) {
  let contents = '';
  try { contents = await readFile(new URL('.env', root), 'utf8'); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  const values = {};
  for (const line of contents.split(/\r?\n/)) {
    const match = line.match(/^\s*(DEERMIND_LLM_\w+)\s*=\s*(.*?)\s*$/);
    if (match) values[match[1]] = match[2].replace(/^(['"])(.*)\1$/, '$2');
  }
  const get = (key, fallback = '') => environment[key] || values[key] || fallback;
  const config = {
    key: get('DEERMIND_LLM_API_KEY'),
    model: get('DEERMIND_LLM_MODEL', 'deepseek-flash'),
    base: get('DEERMIND_LLM_BASE_URL', 'https://api.deepseek.com').replace(/\/$/, ''),
  };
  if (!/^https:\/\/api\.deepseek\.com(?:\/v1)?$/.test(config.base)) {
    throw new Error('Only the previously selected DeepSeek official service is supported.');
  }
  return config;
}
