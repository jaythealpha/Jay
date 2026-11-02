// Stage-1 entry hardening (event.html): in-app browser escape, camera timeout/denial fallbacks,
// reward without camera, funnel beacons. Server calls are mocked.
import { chromium } from 'playwright-core'; import { serve, findChrome, enc, check, done } from './_lib.mjs';
const srv = await serve(8099); const B = 'http://127.0.0.1:8099/event.html?lang=ko#c=';
const br = await chromium.launch({ executablePath: findChrome(), args: ['--no-sandbox'] });
const KAKAO = 'Mozilla/5.0 (Linux; Android 14; SM-S921N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36 KAKAOTALK 10.8.2';
const IGIOS = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 350.0.0';
const coupon = { k: 'coupon', t: '숨은 쿠폰', rx: '10% 할인', rd: 'SCAN10' }, photo = { k: 'photo', t: '포토존', rm: 'capture', rx: '음료 1잔 무료', rd: 'PHOTO1' };
async function open(cfg, { ua, init } = {}) {
  const ctx = await br.newContext({ viewport: { width: 390, height: 800 }, userAgent: ua }); const evs = [], errs = [];
  await ctx.route('**/api/ar-asset**', (r) => { const b = r.request().postData(); if (b) evs.push(JSON.parse(b).n); r.fulfill({ status: 204 }); });
  if (init) await ctx.addInitScript(init);
  const pg = await ctx.newPage(); pg.on('pageerror', (e) => errs.push(e.message)); await pg.goto(B + enc(cfg)); await pg.waitForTimeout(900);
  return { ctx, pg, evs, errs };
}
const vis = (pg, id) => pg.evaluate((id) => getComputedStyle(document.getElementById(id)).display !== 'none', id);
{ const { ctx, pg, evs, errs } = await open(coupon, { ua: KAKAO });
  check('KakaoTalk: in-app banner shown', await vis(pg, 'inapp'));
  check('KakaoTalk: auto-escape attempted once', (await pg.evaluate(() => sessionStorage.getItem('esc_tried'))) === '1' && evs.includes('escape'));
  check('KakaoTalk: beacons land+inapp', evs.includes('land') && evs.includes('inapp'), evs.join(','));
  check('no page errors', !errs.length, errs.join(';')); await ctx.close(); }
{ const { ctx, pg } = await open(coupon, { ua: IGIOS });
  const t = await pg.textContent('#inapp'); check('Instagram iOS: Safari instructions + copy link', /Safari/.test(t) && /링크 복사/.test(t)); await ctx.close(); }
{ const { ctx, pg, evs } = await open(photo, { init: () => { navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('denied', 'NotAllowedError')); } });
  await pg.click('#go'); await pg.waitForTimeout(1200);
  const fb = await pg.textContent('#fb'); check('camera denied: fallback offers reward', /카메라 없이 혜택 받기/.test(fb), fb);
  await pg.click('#fb button:has-text("혜택")'); await pg.waitForTimeout(300);
  check('photo reward without camera', /PHOTO1/.test(await pg.textContent('#reward')));
  check('beacons cam_start,cam_fail,nocam,sheet', ['cam_start', 'cam_fail', 'nocam', 'sheet'].every((n) => evs.includes(n)), evs.join(',')); await ctx.close(); }
{ const { ctx, pg } = await open(coupon, { ua: KAKAO, init: () => { sessionStorage.setItem('esc_tried', '1'); navigator.mediaDevices.getUserMedia = () => new Promise(() => {}); } });
  await pg.click('#go'); await pg.waitForTimeout(13500);
  const fb = await pg.textContent('#fb'); check('camera hang (12s timeout): escape + no-camera + retry offered', /기본 브라우저로 열기/.test(fb) && /카메라 없이 보기/.test(fb) && /다시 시도/.test(fb), fb);
  await ctx.close(); }
await br.close(); srv.close(); done();
