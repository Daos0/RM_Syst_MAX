export const storageKeys = Object.freeze({
  dataVersion: 'sale_prototype_data_version',
  goal: 'sale_goal',
  listSets: 'sale_list_sets',
  legacyCustomLists: 'sale_custom_lists',
  shoppingLists: 'sale_shopping_lists_v1',
  personalCatalog: 'sale_personal_catalog_v1',
  productUsage: 'sale_product_usage_v1',
  recipeUsage: 'sale_recipe_usage_v1'
});

export function resetPrototypeData(version) {
  if (localStorage.getItem(storageKeys.dataVersion) === version) return;
  Object.values(storageKeys)
    .filter((key) => ![storageKeys.dataVersion, storageKeys.personalCatalog].includes(key))
    .forEach((key) => localStorage.removeItem(key));
  localStorage.setItem(storageKeys.dataVersion, version);
}

export function readText(key, fallback = '') {
  return localStorage.getItem(key) || fallback;
}

export function writeText(key, value) {
  localStorage.setItem(key, value);
}

export function readJson(key, fallback = {}) {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
  } catch (_) {
    return fallback;
  }
}

export function writeJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}
