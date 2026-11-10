// In-memory fakes for Vercel Blob + Upstash KV, shared by the action tests (installs globalThis.fetch).
export const blobs = new Map(), kvs = new Map();
export const state = { kvOn: true };
const realFetch = globalThis.fetch;
process.env.BLOB_READ_WRITE_TOKEN = 'test'; process.env.KV_REST_API_URL = 'https://kv.test'; process.env.KV_REST_API_TOKEN = 'k';
globalThis.fetch = async (url, init = {}) => {
  url = String(url); if (url.startsWith('http://127.0.0.1')) return realFetch(url, init); const J = (o, st = 200) => ({ ok: st < 300, status: st, json: async () => o });
  if (url.startsWith('https://kv.test/')) {
    if (!state.kvOn) return J({ error: 'off' }, 500);
    const [cmd, ...a] = url.slice(16).split('/').map(decodeURIComponent);
    if (cmd === 'incr') { const v = (parseInt(kvs.get(a[0]) || '0', 10) + 1); kvs.set(a[0], String(v)); return J({ result: v }); }
    if (cmd === 'get') return J({ result: kvs.has(a[0]) ? kvs.get(a[0]) : null });
    if (cmd === 'set') { if (a[2] === 'NX' && kvs.has(a[0])) return J({ result: null }); kvs.set(a[0], a[1]); return J({ result: 'OK' }); }
    return J({ result: null });
  }
  if (url.startsWith('https://blob.vercel-storage.com/?pathname=')) { const p = new URL(url).searchParams.get('pathname'); blobs.set(p, init.body); return J({ url: 'https://s.public.blob.vercel-storage.com/' + p }); }
  if (url.startsWith('https://blob.vercel-storage.com/?prefix=')) { const pre = new URL(url).searchParams.get('prefix'); return J({ blobs: [...blobs.keys()].filter((k) => k.startsWith(pre)).map((k) => ({ pathname: k, url: 'https://s.public.blob.vercel-storage.com/' + k })) }); }
  if (url === 'https://blob.vercel-storage.com/delete') { JSON.parse(init.body).urls.forEach((u) => blobs.delete(u.split('.com/')[1])); return J({}); }
  if (url.startsWith('https://s.public.blob.vercel-storage.com/')) { const p = url.split('.com/')[1].split('?')[0]; const b = blobs.get(p); return b == null ? J({}, 404) : J(JSON.parse(String(b))); }
  return J({}, 404);
};
