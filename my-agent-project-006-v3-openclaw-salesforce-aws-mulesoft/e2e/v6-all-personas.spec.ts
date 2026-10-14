/**
 * V6 Frontend E2E — All 3 Personas, All Sample Queries
 *
 * Tests the live deployed V6 UI at CloudFront by:
 *  1. Loading each persona page
 *  2. Verifying the UI shell renders (header, nav, input, sample queries panel)
 *  3. Clicking each sample query button and verifying the UI responds
 *
 * This is a "test like a human" suite — it interacts with the real deployed
 * frontend the same way a demo operator would: open the page, expand the
 * sample queries panel, click a query, watch for streaming response.
 *
 * NOTE: The backend is live. Queries hit real Bedrock/Finnhub/Tavily.
 * Some queries may timeout or return partial results — that's expected
 * and documented in the test expectations.
 */

import { test, expect, type Page } from '@playwright/test';

const BASE = 'https://d2zs9nk4uc2dbx.cloudfront.net';

// ─── Helpers ──────────────────────────────────────────────────────────

/** Wait for the V6 root to render and the header to be visible. */
async function waitForV6Shell(page: Page) {
  await expect(page.locator('[data-testid="v6-root"]')).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('header.v6-header')).toBeVisible();
}

/** Expand the "Sample queries" <details> panel if it's closed. */
async function expandSampleQueries(page: Page) {
  const summary = page.locator('.v6-samples summary', { hasText: /^Sample queries/ });
  await summary.click();
  await expect(page.locator('.v6-samples__body')).toBeVisible({ timeout: 3_000 });
}

/** Expand a specific category within the sample queries panel. */
async function expandCategory(page: Page, label: string) {
  const cat = page.locator('.v6-samples__cat-details', {
    has: page.locator(`summary:has-text("${label}")`),
  });
  await expect(cat).toBeVisible();
  const isOpen = await cat.getAttribute('open');
  if (isOpen === null) {
    await cat.locator('summary').click();
  }
  await expect(cat.locator('.v6-samples__cat-body')).toBeVisible();
}

/** Click a sample query button by matching its text. Uses substring match. */
async function clickSampleQuery(page: Page, queryText: string) {
  // Use the first 45 chars to avoid issues with special characters
  const shortText = queryText.slice(0, 45);
  const btn = page.locator('.v6-samples__item').filter({
    has: page.locator(`.v6-samples__item-text`, { hasText: shortText }),
  });
  await expect(btn).toBeVisible({ timeout: 5_000 });
  await btn.click();
}

/**
 * After clicking a sample query, verify the UI shows some response activity.
 *
 * Research: input gets populated, then brief/chips/streaming status appears.
 * Advisor: the sample query calls onSelect which directly submits via send().
 *          Response appears as .v6-msg inside .v6-conversation, or streaming status.
 * Client: the sample query calls emitClientTurn which adds a client bubble
 *         and sends. Response appears as .v6-bubble--in (agent reply).
 */
async function waitForResponse(page: Page, persona: 'research' | 'advisor' | 'client') {
  if (persona === 'research') {
    // Brief starts streaming, running chips appear, or streaming status shows
    await expect(
      page.locator('.v6-brief, .v6-chips, .slds-card__status--streaming').first(),
    ).toBeVisible({ timeout: 45_000 });
  } else if (persona === 'advisor') {
    // The conversation panel shows a .v6-msg (agent response), or streaming status,
    // or the "drafting…" text appears in the conversation header
    await expect(
      page.locator('.v6-msg, .slds-card__status--streaming, .v6-msg__time:has-text("drafting")').first(),
    ).toBeVisible({ timeout: 45_000 });
  } else {
    // Client: a new inbound bubble appears in the WhatsApp thread.
    // The client's own message appears as .v6-bubble--out, agent reply as .v6-bubble--in.
    // We wait for at least 2 .v6-bubble--in (one is the greeting, second is the response)
    // OR we wait for the bubble count to increase.
    await expect(
      page.locator('.v6-bubble--in').nth(1),
    ).toBeVisible({ timeout: 45_000 });
  }
}

/** Take a named screenshot for the report. */
async function snap(page: Page, name: string) {
  await page.screenshot({
    path: `e2e-report/screenshots/${name}.png`,
    fullPage: true,
  });
}

// ─── Test data ────────────────────────────────────────────────────────

interface QueryDef {
  category: string;
  text: string;
  narrative?: boolean;
}

const RESEARCH_QUERIES: QueryDef[] = [
  { category: 'Earnings preview', text: 'Research META ahead of earnings — focus on data-center capex and AI monetization', narrative: true },
  { category: 'Earnings preview', text: 'Research NVDA ahead of earnings — focus on data-center revenue mix and China exposure' },
  { category: 'Earnings preview', text: 'Pre-earnings setup for MSFT — Azure growth vs. consensus' },
  { category: 'Financial statements', text: 'Deep dive on NVIDIA financials — margins, ROIC, and peer comparison' },
  { category: 'Financial statements', text: 'Compare AAPL and MSFT gross margins over the last 4 quarters' },
  { category: 'Sentiment & news', text: 'What is the 30-day news sentiment for NVDA?' },
  { category: 'Sentiment & news', text: 'Summarize recent analyst commentary on META AI spending' },
  { category: 'Cross-asset thesis', text: 'How does the NVDA China export ban affect the broader semiconductor supply chain?' },
  { category: 'Cross-asset thesis', text: 'What is the read-through from TSMC earnings to NVDA and AMD?' },
  { category: 'Filing deep-dive', text: 'What are the key risk factors in NVDA latest 10-K?', narrative: true },
  { category: 'Filing deep-dive', text: 'Summarize Item 7 MD&A from AAPL most recent 10-Q' },
  { category: 'Quick check', text: 'Quote NVDA' },
  { category: 'Quick check', text: 'Who covers NVDA on our desk?' },
  { category: 'Quick check', text: 'Is NVDA on the restricted list?' },
];

const ADVISOR_QUERIES: QueryDef[] = [
  { category: 'Trade orders', text: 'Trim Patel META from 6.8% to 4.5% of equity sleeve', narrative: true },
  { category: 'Trade orders', text: 'Trim NVDA from 14.2% to 9.5% for Eleanor Vance', narrative: true },
  { category: 'Trade orders', text: 'Buy 500 shares of MSFT for the Chen household' },
  { category: 'Wire transfers', text: 'Initiate a $50,000 wire from Patel account to external bank' },
  { category: 'Portfolio review', text: 'Show me the Patel household concentration report' },
  { category: 'Portfolio review', text: 'What is Eleanor Vance current allocation vs IPS?' },
  { category: 'Suitability', text: 'Run suitability check on a 10% NVDA position for Nakamura' },
  { category: 'Suitability', text: 'Is a concentrated tech position suitable for the Al-Rashid household?' },
  { category: 'Research awareness', text: 'What did Sarah publish on NVDA this week?' },
  { category: 'Research awareness', text: 'Any new research briefs relevant to the Patel portfolio?' },
  { category: 'General', text: 'Schedule a call with Eleanor Vance for Thursday 2pm' },
  { category: 'General', text: 'Draft a follow-up email to the Patel family about the META trim' },
];

const CLIENT_QUERIES: QueryDef[] = [
  { category: 'FAQ — fast answers', text: 'What are your office hours?' },
  { category: 'FAQ — fast answers', text: 'How do I update my contact information?' },
  { category: 'FAQ — fast answers', text: 'What is the minimum investment amount?' },
  { category: 'FAQ — scheduling', text: 'Please schedule a call with my RM' },
  { category: 'FAQ — scheduling', text: 'Can I meet with my advisor next week?' },
  { category: 'Escalation — concern', text: 'Should I be worried about META?', narrative: true },
  { category: 'Escalation — concern', text: 'I keep seeing headlines about chip export bans. Is my portfolio affected?' },
  { category: 'Escalation — concern', text: 'Can you tell me my current portfolio value?' },
  { category: 'Escalation — action request', text: 'I want to sell all my NVDA shares', narrative: true },
  { category: 'Escalation — action request', text: 'Please lock in my gains on META before earnings' },
];

// ═══════════════════════════════════════════════════════════════════════
// PERSONA 1: Sarah Chen — Research Analyst (14 queries)
// ═══════════════════════════════════════════════════════════════════════

test.describe('Persona 1: Sarah Chen — Research Analyst', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/?persona=research&v6=1`);
    await waitForV6Shell(page);
  });

  test('shell renders correctly', async ({ page }) => {
    await expect(page.locator('.v6-header__user')).toContainText('Sarah Chen');
    await expect(page.locator('.v6-header__user-role')).toContainText('Sr. Equity Analyst');
    const researchLink = page.locator('.v6-header__nav a', { hasText: 'Research' });
    await expect(researchLink).toHaveClass(/is-active/);
    await expect(page.locator('input[aria-label="Research query"]')).toBeVisible();
    await expect(page.locator('button.v6-btn--brand')).toBeVisible();
    await expect(page.locator('.v6-samples')).toBeVisible();
    await expect(page.locator('[data-testid="v6-trust-spine"]')).toBeVisible();
    await expect(page.locator('[data-testid="v6-theme-toggle"]')).toBeVisible();
    await snap(page, '01-research-shell');
  });

  test('persona nav links use v6=1', async ({ page }) => {
    await expect(page.locator('.v6-header__nav a', { hasText: 'Advisor' }))
      .toHaveAttribute('href', /persona=advisor.*v6=1/);
    await expect(page.locator('.v6-header__nav a', { hasText: 'Liaison' }))
      .toHaveAttribute('href', /persona=client.*v6=1/);
  });

  test('theme toggle works', async ({ page }) => {
    const toggle = page.locator('[data-testid="v6-theme-toggle"]');
    const root = page.locator('html');
    const initial = await root.getAttribute('data-theme');
    await toggle.click();
    const toggled = await root.getAttribute('data-theme');
    expect(toggled).not.toBe(initial);
    await toggle.click();
    expect(await root.getAttribute('data-theme')).toBe(initial);
  });

  test('sample queries panel expands and shows all 6 categories', async ({ page }) => {
    await expandSampleQueries(page);
    for (const cat of ['Earnings preview', 'Financial statements', 'Sentiment & news',
      'Cross-asset thesis', 'Filing deep-dive', 'Quick check']) {
      await expect(page.locator('.v6-samples__category', { hasText: cat })).toBeVisible();
    }
    await snap(page, '02-research-categories');
  });

  // ── Research query tests ──
  const uniqueCats = [...new Set(RESEARCH_QUERIES.map((q) => q.category))];
  for (const category of uniqueCats) {
    const queries = RESEARCH_QUERIES.filter((q) => q.category === category);
    test.describe(`Category: ${category}`, () => {
      for (const q of queries) {
        test(`query: "${q.text.slice(0, 55)}…"`, async ({ page }) => {
          await expandSampleQueries(page);
          await expandCategory(page, q.category);
          await clickSampleQuery(page, q.text);

          // Research: clicking a sample query populates the input AND auto-submits
          const input = page.locator('input[aria-label="Research query"]');
          await expect(input).toHaveValue(q.text, { timeout: 3_000 });

          // Wait for response
          await waitForResponse(page, 'research');

          const tag = q.text.replace(/[^a-zA-Z0-9]/g, '-').slice(0, 40);
          await snap(page, `research-${tag}`);
        });
      }
    });
  }
});

// ═══════════════════════════════════════════════════════════════════════
// PERSONA 2: Marcus Kerrigan — Wealth Advisor (12 queries)
// ═══════════════════════════════════════════════════════════════════════

test.describe('Persona 2: Marcus Kerrigan — Wealth Advisor', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/?persona=advisor&v6=1`);
    await waitForV6Shell(page);
  });

  test('shell renders correctly', async ({ page }) => {
    await expect(page.locator('.v6-header__user')).toContainText('Marcus Kerrigan');
    await expect(page.locator('.v6-header__user-role')).toContainText('Sr. Wealth Advisor');
    await expect(page.locator('.v6-header__nav a', { hasText: 'Advisor' })).toHaveClass(/is-active/);
    // Advisor uses a textarea for the composer
    await expect(page.locator('textarea[aria-label="Advisor composer"]')).toBeVisible();
    await expect(page.locator('.v6-samples')).toBeVisible();
    // Queues panel
    await expect(page.locator('[aria-label="Queues"]')).toBeVisible();
    // Conversation panel
    await expect(page.locator('[aria-label="Conversation"]')).toBeVisible();
    // Client 360 panel
    await expect(page.locator('[aria-label="Client 360"]')).toBeVisible();
    await snap(page, '03-advisor-shell');
  });

  test('sample queries panel shows all 6 advisor categories', async ({ page }) => {
    await expandSampleQueries(page);
    for (const cat of ['Trade orders', 'Wire transfers', 'Portfolio review',
      'Suitability', 'Research awareness', 'General']) {
      await expect(page.locator('.v6-samples__category', { hasText: cat })).toBeVisible();
    }
    await snap(page, '04-advisor-categories');
  });

  // ── Advisor query tests ──
  const uniqueCats = [...new Set(ADVISOR_QUERIES.map((q) => q.category))];
  for (const category of uniqueCats) {
    const queries = ADVISOR_QUERIES.filter((q) => q.category === category);
    test.describe(`Category: ${category}`, () => {
      for (const q of queries) {
        test(`query: "${q.text.slice(0, 55)}…"`, async ({ page }) => {
          await expandSampleQueries(page);
          await expandCategory(page, q.category);
          await clickSampleQuery(page, q.text);

          // Advisor: clicking a sample query calls onSelect which sets query + submits
          // Wait for the conversation panel to show a response
          await waitForResponse(page, 'advisor');

          const tag = q.text.replace(/[^a-zA-Z0-9]/g, '-').slice(0, 40);
          await snap(page, `advisor-${tag}`);
        });
      }
    });
  }
});

// ═══════════════════════════════════════════════════════════════════════
// PERSONA 3: Eleanor Vance — Client (10 queries)
// ═══════════════════════════════════════════════════════════════════════

test.describe('Persona 3: Eleanor Vance — Client', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/?persona=client&v6=1`);
    await waitForV6Shell(page);
  });

  test('shell renders correctly', async ({ page }) => {
    await expect(page.locator('.v6-header__user')).toContainText('Eleanor Vance');
    await expect(page.locator('.v6-header__nav a', { hasText: 'Liaison' })).toHaveClass(/is-active/);
    await expect(page.locator('.v6-samples')).toBeVisible();
    // Phone bezel
    await expect(page.locator('.v6-phone')).toBeVisible();
    // WhatsApp header
    await expect(page.locator('.v6-wa-header__name')).toContainText('Your Wealth Team');
    // Thread area
    await expect(page.locator('.v6-thread')).toBeVisible();
    // Initial greeting bubble
    await expect(page.locator('.v6-bubble--in').first()).toBeVisible();
    await snap(page, '05-client-shell');
  });

  test('sample queries panel shows all 4 client categories', async ({ page }) => {
    await expandSampleQueries(page);
    for (const cat of ['FAQ — fast answers', 'FAQ — scheduling',
      'Escalation — concern', 'Escalation — action request']) {
      await expect(page.locator('.v6-samples__category', { hasText: cat })).toBeVisible();
    }
    await snap(page, '06-client-categories');
  });

  // ── Client query tests ──
  const uniqueCats = [...new Set(CLIENT_QUERIES.map((q) => q.category))];
  for (const category of uniqueCats) {
    const queries = CLIENT_QUERIES.filter((q) => q.category === category);
    test.describe(`Category: ${category}`, () => {
      for (const q of queries) {
        test(`query: "${q.text.slice(0, 55)}…"`, async ({ page }) => {
          await expandSampleQueries(page);
          await expandCategory(page, q.category);

          await clickSampleQuery(page, q.text);

          // Client: clicking a sample query calls emitClientTurn which:
          //  1. Adds a .v6-bubble--out (client message) — this also removes the
          //     hardcoded greeting because messages.length > 0
          //  2. Sends to backend via WebSocket
          //  3. Agent reply arrives as .v6-bubble--in via appendAgentFromStore

          // Verify the client's outbound bubble appeared
          await expect(page.locator('.v6-bubble--out').last()).toContainText(
            q.text.slice(0, 30),
            { timeout: 5_000 },
          );

          // Wait for an agent response bubble (the greeting is gone now,
          // so any .v6-bubble--in is a real agent response)
          await expect(
            page.locator('.v6-bubble--in').first(),
          ).toBeVisible({ timeout: 45_000 });

          const tag = q.text.replace(/[^a-zA-Z0-9]/g, '-').slice(0, 40);
          await snap(page, `client-${tag}`);
        });
      }
    });
  }
});
