import { chromium } from 'playwright';
import { mkdir, writeFile } from 'fs/promises';
import path from 'path';

const BASE = 'http://localhost:5173';
const OUT = path.resolve('scripts/test-output');

async function snapshot(page, name) {
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: false });
}

async function readState(page) {
  return page.evaluate(() => {
    const overlay = document.querySelector('.login-overlay');
    const h2s = Array.from(document.querySelectorAll('.login-split h2')).map((e) => e.textContent);
    return {
      overlayTransform: overlay ? getComputedStyle(overlay).transform : null,
      overlayTransition: overlay ? getComputedStyle(overlay).transitionDuration : null,
      hasRegisterClass: overlay?.classList.contains('login-overlay--register'),
      welcomeBack: h2s.includes('Welcome back!'),
      startTracking: h2s.includes('Start tracking today'),
      signupBtn: !!Array.from(document.querySelectorAll('button')).find((b) => b.textContent?.includes('No account yet')),
      signinBtn: !!Array.from(document.querySelectorAll('button')).find((b) => b.textContent?.includes('Already have one')),
    };
  });
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const pass = (name, detail) => { results.push({ status: 'PASS', name, detail }); console.log(`PASS  ${name}${detail ? ` — ${detail}` : ''}`); };
const fail = (name, detail) => { results.push({ status: 'FAIL', name, detail }); console.error(`FAIL  ${name}${detail ? ` — ${detail}` : ''}`); };

function translateX(matrix) {
  if (!matrix || matrix === 'none') return 0;
  const m = matrix.match(/matrix\(([^)]+)\)/);
  if (!m) return 0;
  return parseFloat(m[1].split(',')[4]);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  try {
    await page.goto(BASE, { waitUntil: 'networkidle', timeout: 15000 });
    await wait(800);
    await snapshot(page, '01-initial-login');

    const initial = await readState(page);
    if (initial.welcomeBack && initial.signupBtn && !initial.hasRegisterClass) pass('Initial login', 'welcome on right, sign in visible');
    else fail('Initial login', JSON.stringify(initial));

    const overlayLoginX = translateX(initial.overlayTransform);
    if (overlayLoginX > 0) pass('Overlay starts on right', `translateX=${overlayLoginX.toFixed(0)}px`);
    else fail('Overlay starts on right', `translateX=${overlayLoginX}`);

    await page.getByRole('button', { name: /No account yet\? Sign up/i }).click();

    await wait(300);
    const mid = await page.evaluate(() => {
      const o = document.querySelector('.login-overlay');
      return { t: getComputedStyle(o).transform, dur: getComputedStyle(o).transitionDuration };
    });
    await snapshot(page, '02-mid-slide');
    const midX = translateX(mid.t);
    if (midX > 10 && midX < overlayLoginX - 10) pass('Overlay mid-slide', `translateX=${midX.toFixed(0)}px (between 0 and ${overlayLoginX.toFixed(0)})`);
    else fail('Overlay mid-slide', `translateX=${midX}, dur=${mid.dur}`);

    await wait(600);
    await snapshot(page, '03-after-signup');
    const after = await readState(page);
    if (after.startTracking && after.signinBtn && after.hasRegisterClass) pass('After signup', 'welcome on left, sign up visible');
    else fail('After signup', JSON.stringify(after));
    if (translateX(after.overlayTransform) < 5) pass('Overlay ended on left', `translateX=${translateX(after.overlayTransform).toFixed(0)}px`);
    else fail('Overlay ended on left', JSON.stringify(after));

    await page.getByRole('button', { name: /Already have one\? Sign in/i }).click();
    await wait(300);
    const midBack = await page.evaluate(() => getComputedStyle(document.querySelector('.login-overlay')).transform);
    await snapshot(page, '04-mid-slide-back');
    const midBackX = translateX(midBack);
    if (midBackX > 10 && midBackX < overlayLoginX - 10) pass('Overlay mid-slide back', `translateX=${midBackX.toFixed(0)}px`);
    else fail('Overlay mid-slide back', `translateX=${midBackX}`);

    await wait(600);
    await snapshot(page, '05-after-signin');
    const back = await readState(page);
    if (back.welcomeBack && back.signupBtn && !back.hasRegisterClass) pass('After signin', 'back to sign in, welcome on right');
    else fail('After signin', JSON.stringify(back));

    const report = {
      testedAt: new Date().toISOString(),
      results,
      screenshots: ['01-initial-login.png', '02-mid-slide.png', '03-after-signup.png', '04-mid-slide-back.png', '05-after-signin.png'],
    };
    await writeFile(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2));

    const failed = results.filter((r) => r.status === 'FAIL');
    if (failed.length) { console.error(`\n${failed.length} test(s) failed.`); process.exit(1); }
    console.log(`\nAll ${results.length} checks passed.`);
  } catch (err) {
    console.error('Test run error:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main();
