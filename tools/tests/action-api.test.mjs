// api/action.js with in-memory fakes for Vercel Blob and Upstash KV (no network, no browser).
// Run: node tools/tests/action-api.test.mjs
import { check, done } from './_lib.mjs';
import { blobs, state } from './_fakes.mjs';
const { default: h } = await import('../../api/action.js');
async function call(body) { let out; const res = { status(c) { this.c = c; return this; }, json(o) { out = { c: this.c, ...o }; }, setHeader() {}, end() {} };
  await h(body.method === 'GET' ? { method: 'GET', query: body.q, headers: {} } : { method: 'POST', body, headers: {} }, res); return out; }

const DEV1 = 'dev-aaaaaaaaaaaa', DEV2 = 'dev-bbbbbbbbbbbb';
const def = { t: '추억 상자', c: 'ff4d8d', rules: [
  { if: [{ k: 'who', v: 'owner' }], do: [{ a: 'vault.add', scope: 'shared' }] },
  { if: [{ k: 'pass', p: '1234' }], do: [{ a: 'show', title: 'secret' }] },
  { if: [], do: [{ a: 'vault.show', scope: 'shared', mode: 'all' }] },
] };
const c = await call({ op: 'create', def }); check('create returns id + key', /^[a-z2-9]{10}$/.test(c.id) && c.key && c.key.length > 20);
const stored = [...blobs.entries()].find(([k]) => k.startsWith('aq/' + c.id + '/d-'));
check('password stored only as hash', stored && !String(stored[1]).includes('1234') && /"h":"[0-9a-f]{64}"/.test(String(stored[1])));
check('owner key stored only as hash', !String(stored[1]).includes(c.key));

let s = await call({ op: 'scan', id: c.id, key: c.key, dev: DEV1, ctx: {} });
check('owner scan → vault.add (rule 0)', s.who === 'owner' && s.run && s.run.ri === 0 && s.run.do[0].a === 'vault.add');
s = await call({ op: 'scan', id: c.id, dev: DEV2, ctx: {} });
check('visitor scan → asks password first', s.who === 'visitor' && s.need === 'pass' && s.ri === 1);
s = await call({ op: 'scan', id: c.id, dev: DEV2, ctx: { pass: '0000' } });
check('wrong password → falls through to vault.show + badpass flag', s.run && s.run.ri === 2 && s.badpass === true);
s = await call({ op: 'scan', id: c.id, dev: DEV2, ctx: { pass: '1234' } });
check('right password → secret', s.run && s.run.ri === 1 && s.run.do[0].title === 'secret');

const add = await call({ op: 'vault.add', id: c.id, key: c.key, dev: DEV1, ctx: {}, ri: 0, text: '첫 기록' });
check('owner adds to shared vault', add.ok === true);
const deny = await call({ op: 'vault.add', id: c.id, dev: DEV2, ctx: {}, ri: 0, text: 'spam' });
check('visitor cannot add (rule not theirs)', deny.c === 403);
const list = await call({ op: 'vault.list', id: c.id, dev: DEV2, ctx: { pass: '0000' }, ri: 2 });
check('visitor lists shared vault', list.items && list.items.length === 1 && list.items[0].text === '첫 기록');

const up = await call({ op: 'update', id: c.id, key: c.key, def: { ...def, t: '새 이름', rules: def.rules.map((r, i) => i === 1 ? { if: [{ k: 'pass', h: stored ? JSON.parse(String(stored[1])).rules[1].if[0].h : '' }], do: r.do } : r) } });
check('owner update keeps password hash without plain text', up.ok === true);
s = await call({ op: 'scan', id: c.id, dev: DEV2, ctx: { pass: '1234' } });
check('password still works after update', s.run && s.run.ri === 1 && s.t === '새 이름');
check('old definition files cleaned up', [...blobs.keys()].filter((k) => k.startsWith('aq/' + c.id + '/d-')).length === 1);
check('non-owner update rejected', (await call({ op: 'update', id: c.id, key: 'nope', def })).c === 403);

await call({ op: 'onoff', id: c.id, key: c.key, on: false });
s = await call({ op: 'scan', id: c.id, dev: DEV2, ctx: {} }); check('disabled → visitor sees off', s.off === true && !s.run);
s = await call({ op: 'scan', id: c.id, key: c.key, dev: DEV1, ctx: {} }); check('disabled → owner still runs rules', s.off === true && s.run);

// first-come: count + once
const fc = await call({ op: 'create', def: { t: '선착순', rules: [{ if: [{ k: 'count', from: 1, to: 2 }], do: [{ a: 'show', title: 'win' }] }, { if: [], do: [{ a: 'show', title: 'closed' }] }] } });
const r1 = await call({ op: 'scan', id: fc.id, dev: DEV1, ctx: {} }), r2 = await call({ op: 'scan', id: fc.id, dev: DEV2, ctx: {} }), r3 = await call({ op: 'scan', id: fc.id, dev: DEV2, ctx: {} });
check('count 1–2 → first two win, third closed', r1.run.do[0].title === 'win' && r2.run.do[0].title === 'win' && r3.run.do[0].title === 'closed');
const on = await call({ op: 'create', def: { t: 'once', rules: [{ if: [{ k: 'once' }], do: [{ a: 'show', title: 'mine' }] }, { if: [], do: [{ a: 'show', title: 'taken' }] }] } });
const o1 = await call({ op: 'scan', id: on.id, dev: DEV1, ctx: {} }), o2 = await call({ op: 'scan', id: on.id, dev: DEV2, ctx: {} }), o3 = await call({ op: 'scan', id: on.id, dev: DEV1, ctx: {} });
check('once: claimer keeps it, others see taken', o1.run.do[0].title === 'mine' && o2.run.do[0].title === 'taken' && o3.run.do[0].title === 'mine');

// time + location
const tm = await call({ op: 'create', def: { t: 'tc', rules: [{ if: [{ k: 'time', from: '2099-01-01T00:00+09:00' }], do: [{ a: 'show', title: 'open' }] }, { if: [], do: [{ a: 'countdown', to: '2099-01-01T00:00+09:00' }] }] } });
s = await call({ op: 'scan', id: tm.id, dev: DEV1, ctx: {} }); check('time capsule locked before date → countdown', s.run.do[0].a === 'countdown');
const nr = await call({ op: 'create', def: { t: 'near', rules: [{ if: [{ k: 'near', lat: 37.5665, lng: 126.978, r: 100 }], do: [{ a: 'show', title: 'here' }] }, { if: [], do: [{ a: 'show', title: 'away' }] }] } });
s = await call({ op: 'scan', id: nr.id, dev: DEV1, ctx: {} }); check('location rule asks for location', s.need === 'loc');
s = await call({ op: 'scan', id: nr.id, dev: DEV1, ctx: { lat: 37.5666, lng: 126.9781, acc: 10 } }); check('inside radius → here', s.run.do[0].title === 'here');
s = await call({ op: 'scan', id: nr.id, dev: DEV1, ctx: { lat: 37.6, lng: 127.1, acc: 10 } }); check('outside radius → away', s.run.do[0].title === 'away');

// without KV: count rules never match and say why
state.kvOn = false; process.env.KV_REST_API_URL = '';
const nk = (await import('../../api/action.js?nokv')).default;
let out; await nk({ method: 'POST', body: { op: 'scan', id: fc.id, dev: DEV1, ctx: {} }, headers: {} }, { status() { return this; }, json(o) { out = o; }, setHeader() {} });
check('no KV: count rule skipped, falls back + flags nokv', out.run && out.run.do[0].title === 'closed' && out.kv === false);
check('bad id rejected', (await call({ op: 'scan', id: 'X', dev: DEV1 })).c === 400);
done();
