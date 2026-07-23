const categories = [
  { slug: 'fare', label: 'Transport' },
  { slug: 'food', label: 'Food' },
  { slug: 'groceries', label: 'Groceries' },
  { slug: 'bills', label: 'Bills & Utilities' },
  { slug: 'shopping', label: 'Shopping' },
  { slug: 'entertainment', label: 'Entertainment' },
  { slug: 'health', label: 'Health' },
  { slug: 'other', label: 'Other' },
];

const totals = {
  fare: 0,
  food: 0,
  groceries: 0,
  bills: 0,
  shopping: 0,
  entertainment: 0,
  health: 0,
  other: 0,
  spent: 0,
  remaining: 2500,
};

export const dashboardResponse = {
  username: 'browser-tester',
  week_info: {
    week_start: '2026-07-19',
    week_end: '2026-07-25',
    week_start_formatted: 'Jul 19',
    week_end_formatted: 'Jul 25',
    current_day: 'Thursday',
    days_remaining: 3,
  },
  budget: {
    allowance: 2500,
    expenses: {},
    totals,
    category_status: {},
    category_limits: {},
    custom_categories: [],
  },
  comparison: null,
  category_rules: [],
  custom_categories: [],
};

export const receiptResponse = {
  receipt: {
    merchant: 'Starbucks',
    purchase_date: '2026-07-23',
    total: 350,
    currency: 'PHP',
  },
  items: [
    {
      name: 'Iced Latte',
      amount: 200,
      category: 'food',
      needs_review: false,
    },
    {
      name: 'Blueberry Muffin',
      amount: 150,
      category: 'food',
      needs_review: false,
    },
  ],
  categories,
  warnings: [],
  mode: 'itemized',
};

function jsonResponse(body, status = 200, headers = {}) {
  return {
    status,
    contentType: 'application/json',
    headers,
    body: JSON.stringify(body),
  };
}

function parseJsonBody(request) {
  try {
    return request.postDataJSON();
  } catch {
    return null;
  }
}

export async function installApiMocks(page, options = {}) {
  const state = {
    authenticated: options.authenticated ?? true,
    rememberMe: false,
    csrfRequests: 0,
    requests: [],
  };
  const handlers = options.handlers || {};

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const key = `${method} ${url.pathname}`;
    const record = {
      key,
      headers: request.headers(),
      json: parseJsonBody(request),
      postData: request.postData(),
    };
    state.requests.push(record);

    if (handlers[key]) {
      const result = await handlers[key]({ request, record, state });
      if (result) {
        await route.fulfill(jsonResponse(
          result.body ?? {},
          result.status ?? 200,
          result.headers ?? {},
        ));
        return;
      }
    }

    if (key === 'GET /api/csrf-token') {
      state.csrfRequests += 1;
      await route.fulfill(jsonResponse({ csrf_token: `csrf-token-${state.csrfRequests}` }));
      return;
    }

    if (key === 'GET /api/check-auth') {
      await route.fulfill(jsonResponse(state.authenticated
        ? {
            authenticated: true,
            username: 'browser-tester',
            remember_me: state.rememberMe,
            onboarding_completed: true,
            is_admin: false,
            receipt_ocr_enabled: true,
          }
        : { authenticated: false }));
      return;
    }

    if (key === 'POST /api/login') {
      state.authenticated = true;
      state.rememberMe = Boolean(record.json?.remember_me);
      await route.fulfill(jsonResponse({ success: true }));
      return;
    }

    if (key === 'GET /api/dashboard') {
      await route.fulfill(jsonResponse(dashboardResponse));
      return;
    }

    if (key === 'GET /api/user-categories') {
      await route.fulfill(jsonResponse({ custom_categories: [] }));
      return;
    }

    if (key === 'GET /api/income-sources') {
      await route.fulfill(jsonResponse({ income_sources: [], income_total: 0 }));
      return;
    }

    if (key === 'GET /api/spending-anomalies') {
      await route.fulfill(jsonResponse({ anomalies: [], sample_size: 0 }));
      return;
    }

    if (key === 'GET /api/insights') {
      await route.fulfill(jsonResponse({ served: true, insights: [] }));
      return;
    }

    if (key === 'POST /api/receipt-scans/extract') {
      await route.fulfill(jsonResponse(receiptResponse));
      return;
    }

    if (key === 'POST /api/expense-items/batch') {
      await route.fulfill(jsonResponse({
        day: record.json?.day,
        expense: {
          total: 350,
          items: (record.json?.items || []).map((item, index) => ({
            id: index + 1,
            ...item,
          })),
        },
        totals: {
          ...totals,
          food: 350,
          spent: 350,
          remaining: 2150,
        },
      }));
      return;
    }

    await route.fulfill(jsonResponse({}));
  });

  return state;
}
