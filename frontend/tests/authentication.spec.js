import { expect, test } from 'playwright/test';
import { installApiMocks } from './support/mockApi';

test.describe('authentication behavior', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('redirects an unverified account to the verification page', async ({ page }) => {
    await installApiMocks(page, {
      authenticated: false,
      handlers: {
        'POST /api/login': async () => ({
          status: 403,
          body: {
            error: 'Verify your email before signing in.',
            verification_required: true,
            email: 'pending@example.test',
          },
        }),
      },
    });

    await page.goto('/');
    await page.locator('input[autocomplete="username"]:visible').fill('pending-user');
    await page.locator('input[autocomplete="current-password"]:visible').fill('Password1!');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page).toHaveURL(/\/verify-email-sent$/);
    await expect(page.getByRole('heading', { name: 'Verify your email' })).toBeVisible();
    await expect(page.getByText('Verify your email before signing in.')).toBeVisible();
    await expect(page.locator('input[autocomplete="email"]')).toHaveValue('pending@example.test');
  });

  test('sends remember-me and opens the weekly dashboard', async ({ page }) => {
    const api = await installApiMocks(page, { authenticated: false });

    await page.goto('/');
    await page.locator('input[autocomplete="username"]:visible').fill('browser-tester');
    await page.locator('input[autocomplete="current-password"]:visible').fill('Password1!');
    await page.getByRole('checkbox', { name: 'Remember me' }).check();
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole('button', { name: 'Scan receipt' })).toBeVisible();

    const loginRequest = api.requests.find((request) => request.key === 'POST /api/login');
    expect(loginRequest?.json).toEqual({
      username: 'browser-tester',
      password: 'Password1!',
      remember_me: true,
    });
  });
});
