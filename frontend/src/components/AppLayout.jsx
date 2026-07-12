import { useState, useEffect, createContext, useContext, useMemo } from 'react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { apiFetch } from '../api';
import { NAV_ITEMS, matchNavItem } from '../utils/nav';
import OnboardingTour from './OnboardingTour';

const ICON = 'h-[22px] w-[22px]';
const svgProps = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  className: ICON,
};

const HomeIcon = () => (
  <svg {...svgProps}>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5" />
  </svg>
);
const ChartIcon = () => (
  <svg {...svgProps}>
    <path d="M3 20h18" />
    <path d="M7 16V8" />
    <path d="M12 16V5" />
    <path d="M17 16v-4" />
  </svg>
);
const BudgetIcon = () => (
  <svg {...svgProps}>
    <rect x="2" y="7" width="20" height="12" rx="2" />
    <circle cx="12" cy="13" r="2.25" />
    <path d="M6 10.5v5M18 10.5v5" />
  </svg>
);
const SavingsIcon = () => (
  <svg {...svgProps}>
    <path d="M19 11a6.5 6.5 0 0 0-6.5-6.5h-3A5.5 5.5 0 0 0 4 10c0 2.4 1.4 4.5 3.4 5.5V19h3.2v-2h2.8v2H16v-3.1c1.2-.7 2.1-1.7 2.5-3" />
    <path d="M16.5 11H20a1.5 1.5 0 0 1 0 3h-3.2" />
    <circle cx="9" cy="10.5" r="0.9" fill="currentColor" stroke="none" />
    <path d="M7.2 19v1.5M13.8 19v1.5" />
  </svg>
);
const ReportsIcon = () => (
  <svg {...svgProps}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
    <path d="M8 13h8" />
    <path d="M8 17h6" />
  </svg>
);
const SettingsIcon = () => (
  <svg {...svgProps}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
  </svg>
);
const SunIcon = () => (
  <svg {...svgProps} className="h-[18px] w-[18px]">
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
  </svg>
);
const MoonIcon = () => (
  <svg {...svgProps} className="h-[18px] w-[18px]">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
  </svg>
);
const LogoutIcon = () => (
  <svg {...svgProps} className="h-[18px] w-[18px]">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5" />
    <path d="M21 12H9" />
  </svg>
);
const MenuIcon = () => (
  <svg {...svgProps} className="h-[18px] w-[18px]">
    <path d="M3 6h18M3 12h18M3 18h18" />
  </svg>
);

const NAV_ICONS = {
  weekly: HomeIcon,
  monthly: ChartIcon,
  reports: ReportsIcon,
  savings: SavingsIcon,
  budget: BudgetIcon,
  settings: SettingsIcon,
};

const LayoutContext = createContext(null);

export function useAppLayout() {
  const ctx = useContext(LayoutContext);
  if (!ctx) throw new Error('useAppLayout must be used within AppLayout');
  return ctx;
}

function SidebarNav({ onNavigate, tourActive }) {
  const linkCls = ({ isActive }) =>
    `app-nav-item ${isActive ? 'app-nav-item--active' : ''} ${tourActive && isActive ? 'ring-1 ring-purple-primary/50' : ''}`;

  return (
    <nav className="flex flex-1 flex-col gap-1 px-2">
      {NAV_ITEMS.map((item) => {
        const Icon = NAV_ICONS[item.id] || HomeIcon;
        return (
          <NavLink
            key={item.id}
            to={item.path}
            end={item.end}
            className={linkCls}
            onClick={onNavigate}
            title={item.label}
          >
            <Icon />
            <span className="app-nav-label">{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [authReady, setAuthReady] = useState(false);
  const [onboardingCompleted, setOnboardingCompleted] = useState(true);
  const [darkMode, setDarkMode] = useState(localStorage.getItem('darkMode') !== 'false');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [headerActions, setHeaderActions] = useState(null);

  const activeNav = matchNavItem(location.pathname);
  const tourActive = authReady && !onboardingCompleted;

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
    document.body.classList.add('app-body');
    return () => document.body.classList.remove('app-body');
  }, [darkMode]);

  useEffect(() => {
    setSidebarOpen(false);
    setHeaderActions(null);
  }, [location.pathname]);

  useEffect(() => {
    let cancelled = false;
    apiFetch('/api/check-auth')
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (!d.authenticated) {
          navigate('/');
          return;
        }
        if (d.username) setUsername(d.username);
        setOnboardingCompleted(Boolean(d.onboarding_completed));
        setAuthReady(true);
      })
      .catch(() => {
        if (!cancelled) navigate('/');
      });
    return () => { cancelled = true; };
  }, [navigate]);

  const toggleTheme = () => {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem('darkMode', next);
  };

  const logout = async () => {
    await apiFetch('/api/logout', { method: 'POST' });
    navigate('/');
  };

  const outletContext = useMemo(
    () => ({
      setHeaderActions,
      username,
      markOnboardingDone: () => setOnboardingCompleted(true),
      onboardingActive: tourActive,
    }),
    [username, tourActive],
  );

  if (!authReady) {
    return (
      <div className="app-shell flex min-h-screen items-center justify-center">
        <p className="text-sm text-purple-soft">Loading…</p>
      </div>
    );
  }

  return (
    <LayoutContext.Provider value={outletContext}>
      <div className="app-shell">
        <div
          className={`app-sidebar-backdrop ${sidebarOpen ? 'app-sidebar-backdrop--open' : ''}`}
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />

        <aside className={`app-sidebar ${sidebarOpen ? 'app-sidebar--open' : ''}`}>
          <div className="app-sidebar-brand">
            <div className="app-sidebar-logo">
              <span>₱</span>
            </div>
            <span className="app-sidebar-title">Budget</span>
          </div>

          <SidebarNav
            onNavigate={() => setSidebarOpen(false)}
            tourActive={tourActive}
          />

          <div className="app-sidebar-footer">
            {username && (
              <p className="app-sidebar-user" title={username}>
                {username}
              </p>
            )}
            <button
              type="button"
              className="app-sidebar-action"
              onClick={toggleTheme}
              aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
              title={darkMode ? 'Light mode' : 'Dark mode'}
            >
              {darkMode ? <SunIcon /> : <MoonIcon />}
            </button>
            <button
              type="button"
              className="app-sidebar-action app-sidebar-action--danger"
              onClick={logout}
              aria-label="Logout"
              title="Logout"
            >
              <LogoutIcon />
            </button>
          </div>
        </aside>

        <div className="app-main">
          <header className="app-header">
            <div className="flex min-w-0 flex-1 items-start gap-3">
              <button
                type="button"
                className="app-mobile-menu-btn flex lg:hidden"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open menu"
              >
                <MenuIcon />
              </button>
              <div className="min-w-0">
                <h1 className="app-page-title">{activeNav?.title}</h1>
                {activeNav?.subtitle && (
                  <p className="app-page-subtitle">{activeNav.subtitle}</p>
                )}
              </div>
            </div>
            {headerActions && (
              <div className="app-header-actions">{headerActions}</div>
            )}
          </header>

          <main className={`app-content ${tourActive ? 'pb-44' : ''}`}>
            <Outlet context={outletContext} />
          </main>
        </div>

        {tourActive && (
          <OnboardingTour
            username={username}
            onComplete={() => setOnboardingCompleted(true)}
          />
        )}
      </div>
    </LayoutContext.Provider>
  );
}
