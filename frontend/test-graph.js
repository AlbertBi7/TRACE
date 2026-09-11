import { chromium } from 'playwright';
const BASE = 'http://localhost:5173';
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('CONSOLE:', msg.text()));
  page.on('pageerror', err => console.log('PAGEERROR:', err.message));
  page.on('response', async resp => {
    const url = resp.url();
    if (url.includes('/api/cases') && url.includes('/graph')) {
      console.log('RESPONSE', resp.status(), url);
      try { const t = await resp.text(); console.log('BODY', t.slice(0,500)); } catch {}
    }
  });
  await page.goto(BASE + '/login');
  await page.getByLabel('Email Address').fill('investigator@trace.dev');
  await page.getByLabel('Password').fill('TraceInvestigator123!');
  await page.getByRole('button', {name: 'Sign In'}).click();
  await page.waitForTimeout(2000);
  // go to demo case graph
  const caseId = '453bbef1-03fd-428e-9f35-5275c7e3d8a0';
  await page.goto(BASE + `/dashboard/cases/${caseId}/graph`);
  await page.waitForTimeout(5000);
  // check header
  const header = await page.textContent('h2');
  console.log('HEADER:', header);
  const nodesText = await page.locator('text=/nodes/').textContent().catch(()=> 'no nodes text');
  console.log('NODES_TEXT:', nodesText);
  // debug container size
  const size = await page.evaluate(() => {
    const el = document.querySelector('div.absolute.inset-0');
    if (!el) return {found:false};
    const r = el.getBoundingClientRect();
    return {found:true,w:r.width,h:r.height, clientW:el.clientWidth, clientH:el.clientHeight, parent:el.parentElement.getBoundingClientRect(), hasCy:!!window.__traceCy, innerHTML: el.parentElement.innerHTML.slice(0,500)};
  });
  console.log('CONTAINER SIZE', JSON.stringify(size,null,2));
  const manual = await page.evaluate(async () => {
    try {
      const el = document.querySelector('div.absolute.inset-0');
      // try dynamic import cytoscape
      const mod = await import('cytoscape');
      const cytoscape = mod.default;
      const cy = cytoscape({container: el, elements: [{data:{id:'a'}}, {data:{id:'b'}}, {data:{id:'ab', source:'a', target:'b'}}]});
      return {ok:true, hasCy: !!cy, els: cy.elements().length};
    } catch(e) {
      return {ok:false, error: e.message, stack: e.stack};
    }
  });
  console.log('MANUAL CY', JSON.stringify(manual,null,2));
  // check cytoscape
  let hasCy = await page.evaluate(() => !!window.__traceCy);
  console.log('hasCy', hasCy);
  // wait for elements
  for (let i=0; i<10 && !hasCy; i++) {
    await page.waitForTimeout(500);
    hasCy = await page.evaluate(() => !!window.__traceCy);
  }
  await page.waitForTimeout(1000);
  if (hasCy) {
    const info = await page.evaluate(() => {
      const cy = window.__traceCy;
      return {
        elements: cy.elements().length,
        nodes: cy.nodes().length,
        edges: cy.edges().length,
        containerSize: [cy.container().clientWidth, cy.container().clientHeight],
        zoom: cy.zoom(),
        pan: cy.pan()
      };
    });
    console.log('CY INFO', JSON.stringify(info));
    // take screenshot
    await page.screenshot({path: 'frontend/graph-screenshot.png', fullPage: true});
    console.log('screenshot saved');
  } else {
    await page.screenshot({path: 'frontend/graph-screenshot-blank.png', fullPage: true});
    console.log('blank screenshot saved, no cy');
  }
  // network
  await browser.close();
})();
