import {productCatalog, unitSteps} from './catalog.js?v=20260720-database-catalog';
import {groceryCatalog, groceryGroups, groceryItemByName} from './grocery.js?v=20260720-database-catalog';
import {supplyGroups, supplyItemByName} from './supplies.js?v=20260720-database-catalog';

export function createId() {
  return `item_${Date.now()}_${Math.random().toString(36).slice(2,9)}`;
}

export function catalogDefaults(name) {
  const groceryItem = groceryItemByName(name);
  if (groceryItem) return {
    productId: groceryItem.id,
    category: groceryGroups.find((group) => group.id === groceryItem.group)?.name || 'Другое',
    quantity: groceryItem.quantity,
    unit: groceryItem.unit
  };
  const catalogItem = productCatalog[name.trim().toLocaleLowerCase('ru').replaceAll('ё', 'е')];
  if (catalogItem) return {...catalogItem, productId: catalogItem.id};
  const supplyItem = supplyItemByName(name);
  if (supplyItem) return {
    productId: supplyItem.id,
    category: supplyItem.department || supplyGroups.find((group) => group.id === supplyItem.group)?.department || 'Другое',
    quantity: supplyItem.quantity,
    unit: supplyItem.unit
  };
  return {
    productId: null,
    category: 'Другое',
    quantity: 1,
    unit: 'шт.'
  };
}

export function createProduct(name) {
  const defaults = catalogDefaults(name);
  return {
    id: createId(),
    productId: defaults.productId,
    name,
    category: defaults.category,
    quantity: defaults.quantity,
    unit: defaults.unit,
    step: unitSteps[defaults.unit],
    status: 'active',
    mark: '',
    note: ''
  };
}

export function formatQuantity(value) {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2))).replace('.', ',');
}

export function autocompleteCandidates(productUsage) {
  const candidates = new Map();
  Object.keys(productCatalog).forEach((key) => {
    const name = `${key.charAt(0).toLocaleUpperCase('ru')}${key.slice(1)}`;
    candidates.set(key, {name, count: 0});
  });
  groceryCatalog.forEach((item) => {
    const key = item.name.toLocaleLowerCase('ru');
    if (!candidates.has(key)) candidates.set(key, {name: item.name, count: 0});
  });
  Object.entries(productUsage).forEach(([key, item]) => {
    if (!item || typeof item.name !== 'string') return;
    candidates.set(key, {name: item.name.trim(), count: Number(item.count) || 0});
  });
  return [...candidates.values()];
}
