import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
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
  const customCategoriesRef = useRef(customCategories);
  customCategoriesRef.current = customCategories;

  const refreshCustomCategories = useCallback(async () => {
    const res = await apiFetch('/api/user-categories');
    if (!res.ok) return customCategoriesRef.current;
    const data = await res.json();
    const next = data.custom_categories || [];
    setCustomCategories(next);
    return next;
  }, []);

  useEffect(() => {
    refreshCustomCategories().catch(() => {});
  }, [refreshCustomCategories]);

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
