import {groceryItemByName} from './grocery.js?v=20260720-database-catalog';
import {autocompleteCandidates, catalogDefaults, formatQuantity} from './products.js?v=20260720-personal-catalog';
import {supplyCatalog, supplyGroups} from './supplies.js?v=20260720-database-catalog';

export function createUnifiedSearch({getPersonalCatalog, getProductUsage, onChoose, onCreateProduct}) {
  const input = document.getElementById('product-query');
  const autocomplete = document.getElementById('product-autocomplete');

  function hide() {
    autocomplete.classList.add('hidden');
    autocomplete.replaceChildren();
  }

  function matches(query, limit = 24) {
    const normalized = query.trim().toLocaleLowerCase('ru');
    if (normalized.length < 2) return [];
    const productUsage = getProductUsage();
    const products = autocompleteCandidates(productUsage).map((item) => {
      const groceryItem = groceryItemByName(item.name);
      const defaults = catalogDefaults(item.name);
      return {kind: 'product', typeLabel: 'Товар', name: item.name, icon: groceryItem?.icon || '🛒', detail: `${defaults.category} · ${formatQuantity(defaults.quantity)} ${defaults.unit}`, usage: Number(item.count) || 0};
    });
    const personalProducts = Object.values(getPersonalCatalog()).map((item) => ({
      kind: 'product',
      source: 'personal',
      typeLabel: 'Личное',
      name: item.name,
      icon: '🛒',
      detail: `${item.category} · ${formatQuantity(Number(item.quantity))} ${item.unit}`,
      quantity: Number(item.quantity),
      unit: item.unit,
      category: item.category,
      usage: Number(item.addCount) || 0
    }));
    const personalNames = new Set(
      personalProducts.map((item) => item.name.toLocaleLowerCase('ru').replaceAll('ё', 'е'))
    );
    const catalogProducts = products.filter(
      (item) => !personalNames.has(item.name.toLocaleLowerCase('ru').replaceAll('ё', 'е'))
    );
    const supplies = supplyCatalog.map((item) => ({
      kind: 'supply', typeLabel: 'Для дома', id: item.id, name: item.name, icon: item.icon,
      detail: `${supplyGroups.find((group) => group.id === item.group)?.name || 'Другое'} · ${item.note}`,
      usage: Number(productUsage[item.name.toLocaleLowerCase('ru')]?.count) || 0
    }));
    const kindRank = {product: 0, supply: 1};
    return [...personalProducts, ...catalogProducts, ...supplies]
      .filter((item) => item.name.toLocaleLowerCase('ru').includes(normalized))
      .sort((first, second) => {
        const firstName = first.name.toLocaleLowerCase('ru');
        const secondName = second.name.toLocaleLowerCase('ru');
        const firstMatch = firstName === normalized ? 0 : firstName.startsWith(normalized) ? 1 : 2;
        const secondMatch = secondName === normalized ? 0 : secondName.startsWith(normalized) ? 1 : 2;
        return firstMatch - secondMatch || kindRank[first.kind] - kindRank[second.kind]
          || second.usage - first.usage || first.name.localeCompare(second.name, 'ru');
      })
      .slice(0, limit);
  }

  function createProductAction(query, inline = false) {
    const button = document.createElement('button');
    button.className = `global-search-create${inline ? ' inline' : ''}`;
    button.type = 'button';
    if (inline) {
      const icon = document.createElement('span');
      icon.textContent = '+';
      const copy = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = `Добавить «${query}»`;
      const note = document.createElement('small');
      note.textContent = 'Как новый товар';
      copy.append(title, note);
      button.append(icon, copy);
    } else {
      button.textContent = `Добавить «${query}» как новый товар`;
    }
    button.addEventListener('click', () => {
      hide();
      onCreateProduct(query);
    });
    return button;
  }

  function render(query) {
    const normalized = query.trim().toLocaleLowerCase('ru');
    if (normalized.length < 2) {
      hide();
      return;
    }
    const found = matches(query);
    autocomplete.replaceChildren();
    if (!found.length) {
      const empty = document.createElement('div');
      empty.className = 'global-search-empty';
      const title = document.createElement('strong');
      title.textContent = 'В каталоге пока ничего нет';
      const note = document.createElement('small');
      note.textContent = 'Можно добавить собственный товар и настроить количество';
      const create = createProductAction(query.trim());
      empty.append(title, note, create);
      autocomplete.append(empty);
      autocomplete.classList.remove('hidden');
      return;
    }
    const exactExists = found.some(
      (item) => item.name.toLocaleLowerCase('ru') === normalized
    );
    if (!exactExists) autocomplete.append(createProductAction(query.trim(), true));
    found.forEach((item) => {
      const option = document.createElement('button');
      option.className = 'global-search-option';
      option.type = 'button';
      option.setAttribute('role', 'option');
      option.dataset.kind = item.kind;
      const icon = document.createElement('span');
      icon.className = 'global-search-icon';
      icon.textContent = item.icon;
      const copy = document.createElement('span');
      copy.className = 'global-search-copy';
      const name = document.createElement('strong');
      name.textContent = item.name;
      const detail = document.createElement('small');
      detail.textContent = item.detail;
      copy.append(name, detail);
      const kind = document.createElement('span');
      kind.className = 'global-search-kind';
      kind.textContent = item.typeLabel;
      option.append(icon, copy, kind);
      option.addEventListener('click', () => {
        hide();
        onChoose(item);
      });
      autocomplete.append(option);
    });
    autocomplete.classList.remove('hidden');
  }

  function activate(query) {
    const name = query.trim();
    if (!name) return;
    const normalized = name.toLocaleLowerCase('ru');
    const found = matches(name);
    const exact = found.find((item) => item.name.toLocaleLowerCase('ru') === normalized);
    if (exact) {
      hide();
      onChoose(exact);
    } else if (found.length) render(name);
    else onCreateProduct(name);
  }

  return {activate, hide, matches, render, input};
}
