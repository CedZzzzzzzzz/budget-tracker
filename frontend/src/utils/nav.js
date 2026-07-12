export const NAV_ITEMS = [
  {
    id: 'weekly',
    path: '/dashboard',
    label: 'Weekly',
    title: 'Weekly Budget',
    subtitle: 'Track daily spending and stay on budget',
    end: true,
  },
  {
    id: 'monthly',
    path: '/dashboard/monthly',
    label: 'Monthly',
    title: 'Monthly Summary',
    subtitle: 'Review spending trends across the month',
  },
  {
    id: 'reports',
    path: '/reports',
    label: 'Reports',
    title: 'Reports',
    subtitle: 'Custom date ranges and yearly PDF export',
  },
  {
    id: 'savings',
    path: '/savings',
    label: 'Savings',
    title: 'Savings',
    subtitle: 'Goals and running balance of saved weeks',
  },
  {
    id: 'budget',
    path: '/budget',
    label: 'Budget',
    title: 'Budget Setup',
    subtitle: 'Category limits and recurring expenses',
  },
  {
    id: 'settings',
    path: '/settings',
    label: 'Settings',
    title: 'Account Settings',
    subtitle: 'Update your profile or change your password',
  },
];

export function matchNavItem(pathname) {
  if (pathname === '/dashboard/monthly') {
    return NAV_ITEMS.find((item) => item.id === 'monthly');
  }
  if (pathname.startsWith('/dashboard')) {
    return NAV_ITEMS.find((item) => item.id === 'weekly');
  }
  return NAV_ITEMS.find((item) => pathname.startsWith(item.path)) || NAV_ITEMS[0];
}
