/**
 * TRACE — Playwright UI smoke test (Phase 3)
 * One continuous flow: login → create case → upload docs → run extraction →
 * review/accept a merge → graph explorer (sync, layout) → evidentiary drawer →
 * scoped chat with SSE + canvas path highlighting.
 *
 * Requires the live stack (http://localhost:5173):
 *   cd infra && docker compose up -d
 *   cd frontend && npx playwright install chromium && npx playwright test
 */
import { test, expect } from '@playwright/test';

const RUN = Date.now().toString(36).slice(-6);
const CASE_NAME = `UI Smoke ${RUN}`;

const DOC1 = {
  name: 'brief.txt',
  mime: 'text/plain',
  body:
    'Smoke test brief (fictional training data).\n\n' +
    'Nikhil Rao uses phone +91-93111-22233.\n\n' +
    'Nikhil Rao transferred funds from account HDFC-XXXX-5581 to account SBI-XXXX-6692.\n',
};
const DOC2 = {
  name: 'witness.txt',
  mime: 'text/plain',
  body:
    'Witness statement: Nikhil Rau was seen with phone +91-93111-22233 near the depot.\n',
};

test.describe.serial('TRACE UI smoke', () => {
  let caseUrl;

  test('login as investigator', async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('Email Address').fill('investigator@trace.dev');
    await page.getByLabel('Password').fill('TraceInvestigator123!');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByRole('heading', { name: 'Cases', exact: true })).toBeVisible();
  });

  test('create case and upload documents', async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('Email Address').fill('investigator@trace.dev');
    await page.getByLabel('Password').fill('TraceInvestigator123!');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByRole('heading', { name: 'Cases', exact: true })).toBeVisible();

    await page.getByRole('button', { name: /New Case/i }).click();
    await page.getByPlaceholder('e.g., Operation Nexus').fill(CASE_NAME);
    await page.getByPlaceholder('Brief description of the investigation...').fill('UI smoke test case');
    await page.getByRole('button', { name: 'Create Case' }).click();
    await page.getByRole('heading', { name: CASE_NAME }).click();
    await expect(page.getByRole('button', { name: 'Open Graph Explorer' })).toBeVisible();
    caseUrl = page.url();

    await page.setInputFiles('input[type="file"]', [
      { name: DOC1.name, mimeType: DOC1.mime, buffer: Buffer.from(DOC1.body, 'utf8') },
      { name: DOC2.name, mimeType: DOC2.mime, buffer: Buffer.from(DOC2.body, 'utf8') },
    ]);
    await expect(page.getByText(DOC1.name)).toBeVisible();
    await expect(page.getByText(DOC2.name)).toBeVisible();
  });

  test('run extraction on both documents', async ({ page }) => {
    await page.goto(caseUrl);
    for (const doc of [DOC1, DOC2]) {
      const row = page.locator('div', { has: page.getByText(doc.name, { exact: true }) })
        .filter({ has: page.getByRole('button', { name: 'Extract' }) }).first();
      await row.getByRole('button', { name: 'Extract' }).click();
    }
    await expect(page.getByText('Extracted')).toHaveCount(2, { timeout: 60_000 });
  });

  test('review and accept merge suggestion', async ({ page }) => {
    await page.goto(caseUrl);
    await page.getByRole('button', { name: 'Find Matches' }).click();
    const suggestion = page.locator('div').filter({ hasText: /≈/ }).first();
    await expect(suggestion).toBeVisible({ timeout: 30_000 });
    await suggestion.getByRole('button', { name: 'Same entity' }).click();
    await expect(page.getByText(/=/).first()).toBeVisible(); // moved to accepted list
  });

  test('graph explorer renders synced network', async ({ page }) => {
    await page.goto(caseUrl);
    await page.getByRole('button', { name: 'Open Graph Explorer' }).click();
    await page.getByRole('button', { name: /Sync graph/i }).click();
    await expect(page.getByText(/\d+ nodes · \d+ links/)).toBeVisible({ timeout: 30_000 });
    // Force-layout switch is wired to the same Cytoscape instance
    await page.getByRole('button', { name: /Tree layout/i }).click();
    await page.getByRole('button', { name: /Force layout/i }).click();
  });

  test('evidentiary drawer shows verbatim provenance', async ({ page }) => {
    await page.goto(caseUrl);
    await page.getByRole('button', { name: 'Open Graph Explorer' }).click();
    await expect(page.getByText(/\d+ nodes · \d+ links/)).toBeVisible();
    // Click a node on the canvas via the exposed test hook (nodes are canvas-rendered)
    const personId = await page.evaluate(() => {
      const cy = window.__traceCy;
      const n = cy.nodes().filter((n) => n.data('entityType') === 'PERSON')[0];
      return n ? n.id() : null;
    });
    expect(personId).toBeTruthy();
    await page.evaluate((id) => {
      const cy = window.__traceCy;
      const pos = cy.getElementById(id).renderedPosition();
      const rect = cy.container().getBoundingClientRect();
      cy.getElementById(id).emit('tap', { x: pos.x, y: pos.y });
      void rect;
    }, personId);
    const drawer = page.getByText('Source evidence');
    await expect(drawer).toBeVisible();
    await expect(page.getByText(/¶\d+/).first()).toBeVisible();
    await expect(page.getByText(/via (regex|spacy)/)).toBeVisible();
  });

  test('scoped chat answers with citations and highlights path on canvas', async ({ page }) => {
    await page.goto(caseUrl);
    await page.getByRole('button', { name: 'Open Graph Explorer' }).click();
    await expect(page.getByText(/\d+ nodes · \d+ links/)).toBeVisible();

    await page.getByRole('button', { name: 'Analyze' }).click();
    await page.getByRole('button', { name: /Connections Chat/i }).click();
    await page.getByPlaceholder('How is X connected to Y?').fill('how does nikhil connect to SBI-XXXX-6692');
    await page.getByRole('button', { name: 'Send' }).click();

    // Streamed, grounded answer
    await expect(page.getByText(/connected through \d+ step/i)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('Sources')).toBeVisible();
    await expect(page.getByText(/brief\.txt|witness\.txt/).first()).toBeVisible();

    // Canvas highlight applied by the citations event (node_ids path)
    const highlighted = await page.evaluate(() => window.__traceCy.elements('[class~="highlighted"]').length);
    expect(highlighted).toBeGreaterThan(0);
  });
});
