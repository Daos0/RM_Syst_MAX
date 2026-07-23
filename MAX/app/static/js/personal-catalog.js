export function personalCatalogKey(name) {
  return String(name || '')
    .trim()
    .toLocaleLowerCase('ru')
    .replaceAll('ё', 'е')
    .replace(/\s+/g, ' ');
}

export function rememberPersonalProduct(catalog, product) {
  if (product.productId) return false;
  const key = personalCatalogKey(product.name);
  if (!key) return false;
  const previous = catalog[key] || {};
  catalog[key] = {
    name: product.name.trim(),
    quantity: Number(product.quantity),
    unit: product.unit,
    category: product.category,
    addCount: (Number(previous.addCount) || 0) + 1,
    lastAddedAt: new Date().toISOString()
  };
  return true;
}
