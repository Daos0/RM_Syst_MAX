export const supplyGroups = [];
export const supplyCatalog = [];

export function hydrateSupplyCatalog(categories, products) {
  const groups = categories
    .filter((category) => category.kind === 'supply')
    .sort((first, second) => first.sort_order - second.sort_order)
    .map((category) => ({
      id: category.code,
      name: category.name,
      icon: category.icon,
      department: category.description
    }));
  const items = products
    .filter((item) => item.kind === 'supply' && item.category_code)
    .sort((first, second) => first.sort_order - second.sort_order)
    .map((item) => ({
      id: item.id,
      name: item.name,
      group: item.category_code,
      icon: item.icon,
      note: item.description,
      quantity: Number(item.quantity),
      unit: item.unit,
      department: item.department
    }));
  supplyGroups.splice(0, supplyGroups.length, ...groups);
  supplyCatalog.splice(0, supplyCatalog.length, ...items);
}

export function supplyItemByName(name) {
  const normalized = name.trim().toLocaleLowerCase('ru').replaceAll('ё', 'е');
  return supplyCatalog.find((item) => item.name.toLocaleLowerCase('ru').replaceAll('ё', 'е') === normalized) || null;
}
