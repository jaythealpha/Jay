// Action Key QR end to end: studio builder → real api/action.js (in-process, in-memory Blob/KV) → action.html
// as owner and as visitor. Run: node tools/tests/action-ui.test.mjs
import { chromium } from 'playwright-core'; import { serve, findChrome, check, done } from './_lib.mjs';
import { state } from './_fakes.mjs';
const { default: handler } = await import('../../api/action.js');
const srv = await serve(8099); const B = 'http://127.0.0.1:8099';
const br = await chromium.launch({ executablePath: findChrome(), args: ['--no-sandbox'] });
async function apiRoute(route) {
  const rq = route.request(), u = new URL(rq.url()); let out = { c: 200, body: {} };
  const res = { status(c) { out.c = c; return this; }, json(o) { out.body = o; }, setHeader() {}, end() {} };
  await handler(rq.method() === 'GET' ? { method: 'GET', query: Object.fromEntries(u.searchParams), headers: {} } : { method: 'POST', body: rq.postData() || '{}', headers: {} }, res);
  await route.fulfill({ status: out.c, contentType: 'application/json', body: JSON.stringify(out.body) });
}
async function ctxNew(vp = { width: 1280, height: 1500 }) {
  const ctx = await br.newContext({ viewport: vp }); await ctx.route('**/api/action**', apiRoute);
  await ctx.addInitScript(() => { try { localStorage.setItem('aqr_onboarded_v1', '1'); } catch (e) {} }); return ctx;
}
const errs = []; const watch = (pg) => pg.on('pageerror', (e) => errs.push(e.message));

// ---- owner builds a memory box ----
const owner = await ctxNew(); const pg = await owner.newPage(); watch(pg);
await pg.goto(B + '/qr-studio.html?lang=ko#action'); await pg.waitForTimeout(800);
check('action view opens from #action', await pg.isVisible('#view-action'));
await pg.click('[data-tpl="memory"]'); await pg.waitForTimeout(300);
check('template fills two rules', (await pg.$$('.aq-rule')).length === 2);
await pg.click('#aqSave'); await pg.waitForTimeout(1500);
const id = await pg.evaluate(() => (JSON.parse(localStorage.getItem('aq_mine') || '[]')[0] || {}).id);
check('saved → id + owner key stored locally', /^[a-z2-9]{10}$/.test(id || '') && !!(await pg.evaluate((i) => localStorage.getItem('aqk_' + i), id)));
check('link uses /a/<id>', (await pg.textContent('#aqLink')).includes('/a/' + id));
const pvTxt = await pg.frameLocator('#aqPrev').locator('#out').innerText(); check('preview shows owner action (vault.add)', /보관함|사진|오늘의 한 장/.test(pvTxt), pvTxt.slice(0, 60));
await pg.screenshot({ path: process.env.SHOT_DIR ? process.env.SHOT_DIR + '/aq-builder.png' : '/dev/null', fullPage: false });

// owner scans their own QR and leaves a note
const op = await owner.newPage(); watch(op);
await op.goto(B + '/action.html?i=' + id + '&lang=ko'); await op.waitForTimeout(700);
check('owner bar visible', await op.isVisible('#owner'));
await op.fill('[data-t]', '첫 번째 추억'); await op.click('[data-s]'); await op.waitForTimeout(800);
check('owner saved a note to the shared box', /저장했어요/.test(await op.textContent('[data-s]')));

// ---- a visitor scans ----
const vis = await ctxNew({ width: 390, height: 800 }); const vp = await vis.newPage(); watch(vp);
await vp.goto(B + '/action.html?i=' + id + '&lang=ko'); await vp.waitForTimeout(900);
check('visitor: no owner bar', !(await vp.isVisible('#owner')));
check('visitor sees the shared note', (await vp.textContent('#out')).includes('첫 번째 추억'));
await vp.screenshot({ path: process.env.SHOT_DIR ? process.env.SHOT_DIR + '/aq-visitor.png' : '/dev/null' });

// ---- secret message (password) ----
await pg.bringToFront(); await pg.click('[data-tpl="secret"]', { force: true }); pg.once('dialog', (d) => d.accept()); await pg.waitForTimeout(300);
pg.once('dialog', (d) => d.accept());
const pass = await pg.$('.aq-rule input[data-ty="pw"]'); await pass.fill('2580'); await pg.click('#aqSave'); await pg.waitForTimeout(1500);
const id2 = await pg.evaluate(() => JSON.parse(localStorage.getItem('aq_mine'))[0].id);
await vp.goto(B + '/action.html?i=' + id2 + '&lang=ko'); await vp.waitForTimeout(700);
check('visitor asked for password', await vp.isVisible('#pw'));
await vp.fill('#pw', '1111'); await vp.click('#pwGo'); await vp.waitForTimeout(700);
check('wrong password → warning + fallback', /비밀번호가 맞지 않아요/.test(await vp.textContent('#out')));
await vp.goto(B + '/action.html?i=' + id2 + '&lang=ko'); await vp.waitForTimeout(600); await vp.fill('#pw', '2580'); await vp.click('#pwGo'); await vp.waitForTimeout(700);
check('right password → secret message', /비밀 메시지/.test(await vp.textContent('#out')));

// ---- turn off → visitor sees resting ----
await pg.click('#aqManage .toggle'); await pg.waitForTimeout(900);
await vp.goto(B + '/action.html?i=' + id2 + '&lang=ko'); await vp.waitForTimeout(700);
check('disabled QR → visitor sees resting', /쉬고 있어요/.test(await vp.textContent('#out')));

// ---- gift box (future date) → countdown; detox → focus overlay ----
await pg.click('[data-tpl="gift"]', { force: true }); await pg.waitForTimeout(300); await pg.click('#aqSave'); await pg.waitForTimeout(1500);
const id3 = await pg.evaluate(() => JSON.parse(localStorage.getItem('aq_mine'))[0].id);
await vp.goto(B + '/action.html?i=' + id3 + '&lang=ko'); await vp.waitForTimeout(800);
check('gift before date → countdown', /열리기까지/.test(await vp.textContent('#out')) && (await vp.$$('.units div')).length === 4);
await pg.click('[data-tpl="detox"]', { force: true }); await pg.waitForTimeout(300); await pg.click('#aqSave'); await pg.waitForTimeout(1500);
const id4 = await pg.evaluate(() => JSON.parse(localStorage.getItem('aq_mine'))[0].id);
await vp.goto(B + '/action.html?i=' + id4 + '&lang=en'); await vp.waitForTimeout(800);
await vp.click('[data-g]'); await vp.waitForTimeout(700);
check('detox starts the focus overlay (English UI)', await vp.isVisible('#focus') && /Focusing|min|:/.test(await vp.textContent('#focus')));

// ---- first-come without KV → skipped with a note; with KV the first scans win ----
await pg.click('[data-tpl="first"]', { force: true }); await pg.waitForTimeout(300); await pg.click('#aqSave'); await pg.waitForTimeout(1500);
const id5 = await pg.evaluate(() => JSON.parse(localStorage.getItem('aq_mine'))[0].id);
await vp.goto(B + '/action.html?i=' + id5 + '&lang=ko'); await vp.waitForTimeout(700);
check('first-come (KV on) → winner', /당첨/.test(await vp.textContent('#out')));

// ---- owner "edit" link opens the editor with the saved rules ----
await op.goto(B + '/qr-studio.html?lang=ko#action=' + id); await op.waitForTimeout(1500);
check('#action=<id> opens the saved QR in the editor', (await op.inputValue('#aqT')).length > 0 && (await op.$$('.aq-rule')).length === 2);
const sw = await vp.evaluate(() => document.documentElement.scrollWidth); check('visitor page fits 390px', sw <= 390, String(sw));
check('no page errors', !errs.length, errs.join(' | '));
await br.close(); srv.close(); done();
