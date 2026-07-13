import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiFetch } from '../api';
import { CATEGORIES, CATEGORY_COLORS, CATEGORY_LABELS, mergeCategoryMeta } from '../utils/categorize';

const CategoriesContext = createContext({
  customCategories: [],
  categories: CATEGORIES,
  labels: CATEGORY_LABELS,
  colors: CATEGORY_COLORS,
  setCustomCategories: () => {},
  refreshCustomCategories: async () => [],
});

export function CategoriesProvider({ children }) {
  const [customCategories, setCustomCategories] = useState([]);

  const refreshCustomCategories = useCallback(async () => {
    const res = await apiFetch('/api/user-categories');
    if (!res.ok) return customCategories;
    const data = await res.json();
    const next = data.custom_categories || [];
    setCustomCategories(next);
    return next;
  }, [customCategories]);

  useEffect(() => {
    refreshCustomCategories().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo(() => {
    const meta = mergeCategoryMeta(customCategories);
    return {
      customCategories,
      categories: meta.categories,
      labels: meta.labels,
      colors: meta.colors,
      setCustomCategories,
      refreshCustomCategories,
    };
  }, [customCategories, refreshCustomCategories]);

  return (
    <CategoriesContext.Provider value={value}>
      {children}
    </CategoriesContext.Provider>
  );
}

export function useCategories() {
  return useContext(CategoriesContext);
}
