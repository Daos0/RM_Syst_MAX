export const groceryGroups = [];
export const groceryCatalog = [];

export function hydrateGroceryCatalog(categories, products) {
  const groups = categories
    .filter((category) => category.kind === 'product')
    .sort((first, second) => first.sort_order - second.sort_order)
    .map((category) => ({id: category.code, name: category.name, icon: category.icon}));
  const items = products
    .filter((item) => item.kind === 'product' && item.category_code)
    .sort((first, second) => first.sort_order - second.sort_order)
    .map((item) => ({
      id: item.id,
      name: item.name,
      group: item.category_code,
      icon: item.icon,
      quantity: Number(item.quantity),
      unit: item.unit,
      department: item.department
    }));
  groceryGroups.splice(0, groceryGroups.length, ...groups);
  groceryCatalog.splice(0, groceryCatalog.length, ...items);
}

export function groceryItemByName(name) {
  const normalized = name.trim().toLocaleLowerCase('ru').replaceAll('ё', 'е');
  return groceryCatalog.find((item) => item.name.toLocaleLowerCase('ru').replaceAll('ё', 'е') === normalized) || null;
}
