import { Buffer } from 'node:buffer';
import { expect, test } from 'playwright/test';
import { installApiMocks, receiptResponse } from './support/mockApi';

async function openWeeklyDashboard(page) {
  await page.clock.setFixedTime(new Date('2026-07-23T12:00:00'));
  await page.addInitScript(() => {
    sessionStorage.setItem('bt_tab_session', '1');
    sessionStorage.setItem('insights_shown', '1');
  });
  await page.goto('/dashboard');
  await expect(page.getByRole('button', { name: 'Scan receipt' })).toBeVisible();
}

async function chooseReceipt(page) {
  await page.getByRole('button', { name: 'Scan receipt' }).click();
  await expect(page.getByRole('dialog', { name: 'Scan a receipt' })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({
    name: 'starbucks-receipt.png',
    mimeType: 'image/png',
    buffer: Buffer.from('synthetic-receipt-image'),
  });
}

test('keeps the user on Weekly while selecting and reviewing a receipt', async ({ page }) => {
  await installApiMocks(page);
  await openWeeklyDashboard(page);
  await chooseReceipt(page);

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText('starbucks-receipt.png')).toBeVisible();
  await page.getByRole('button', { name: 'Extract receipt' }).click();

  await expect(page.getByText('Starbucks', { exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Name' }).nth(0)).toHaveValue('Iced Latte');
  await expect(page.getByRole('textbox', { name: 'Name' }).nth(1)).toHaveValue('Blueberry Muffin');
  await expect(page.getByRole('button', { name: 'Use itemized list' })).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test('saves itemized receipt lines with merchant notes', async ({ page }) => {
  const api = await installApiMocks(page);
  await openWeeklyDashboard(page);
  await chooseReceipt(page);
  await page.getByRole('button', { name: 'Extract receipt' }).click();
  await expect(page.getByRole('textbox', { name: 'Name' }).nth(0)).toHaveValue('Iced Latte');
  await page.getByRole('button', { name: 'Add 2 expenses' }).click();

  await expect(page.getByRole('dialog', { name: 'Scan a receipt' })).toBeHidden();
  const batchRequest = api.requests.find(
    (request) => request.key === 'POST /api/expense-items/batch',
  );
  expect(batchRequest?.json).toEqual({
    day: 'Thursday',
    items: receiptResponse.items.map((item) => ({
      name: item.name,
      amount: item.amount,
      category: item.category,
      notes: 'Merchant: Starbucks',
      tags: [],
    })),
  });
  expect(batchRequest?.headers['idempotency-key']).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
  );
});

test('refreshes an expired CSRF token and retries extraction once', async ({ page }) => {
  let attempts = 0;
  const api = await installApiMocks(page, {
    handlers: {
      'POST /api/receipt-scans/extract': async () => {
        attempts += 1;
        if (attempts === 1) {
          return {
            status: 403,
            body: { error: 'Invalid or missing CSRF token' },
          };
        }
        return { body: receiptResponse };
      },
    },
  });
  await openWeeklyDashboard(page);
  await chooseReceipt(page);
  await page.getByRole('button', { name: 'Extract receipt' }).click();

  await expect(page.getByText('Starbucks', { exact: true })).toBeVisible();
  expect(attempts).toBe(2);
  expect(api.csrfRequests).toBeGreaterThanOrEqual(2);
  const extractionRequests = api.requests.filter(
    (request) => request.key === 'POST /api/receipt-scans/extract',
  );
  const csrfHeaders = extractionRequests.map(
    (request) => request.headers['x-csrf-token'],
  );
  expect(csrfHeaders).toHaveLength(2);
  expect(csrfHeaders[0]).toMatch(/^csrf-token-\d+$/);
  expect(csrfHeaders[1]).toMatch(/^csrf-token-\d+$/);
  expect(csrfHeaders[1]).not.toBe(csrfHeaders[0]);
});
