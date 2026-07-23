import {unitSteps} from './catalog.js?v=20260720-database-catalog';
import {groceryCatalog, groceryGroups, groceryItemByName} from './grocery.js?v=20260720-database-catalog';
import {catalogDefaults, formatQuantity} from './products.js?v=20260720-personal-catalog';
import {recommendedProductNames} from './recommendations.js?v=20260720-other-category';

export function createProductBrowser({getProductUsage, hideSearch, onConfigure}) {
  const nameInput = document.getElementById('product-query');
  const quantityInput = document.getElementById('item-quantity');
  const unitSelect = document.getElementById('item-unit');
  const categorySelect = document.getElementById('item-category');
  const categoryButtons = document.getElementById('product-category-buttons');
  const selectedCategory = document.getElementById('product-selected-category');
  const catalogGrid = document.getElementById('product-catalog-grid');
  let activeGroup = groceryGroups[0].id;

  function setSuggestionSelection(name) {
    const normalized = name.trim().toLocaleLowerCase('ru');
    document.querySelectorAll('.suggestion-chip').forEach((button) => {
      const selected = button.dataset.productName.toLocaleLowerCase('ru') === normalized;
      button.classList.toggle('selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
  }

  function applyDefaults(name, revealDetails = false) {
    const defaults = catalogDefaults(name);
    const groceryItem = groceryItemByName(name);
    if (groceryItem) activeGroup = groceryItem.group;
    nameInput.value = name;
    quantityInput.value = defaults.quantity;
    unitSelect.value = defaults.unit;
    categorySelect.value = defaults.category;
    quantityInput.step = unitSteps[defaults.unit];
    setSuggestionSelection(name);
    renderCategories();
    renderCatalog();
    if (revealDetails) document.querySelector('.product-details-label').scrollIntoView({block: 'nearest', behavior: 'smooth'});
  }

  function renderSuggestions() {
    const fallback = ['Бананы', 'Вода', 'Огурцы', 'Помидоры', 'Рис', 'Молоко', 'Хлеб', 'Яйца', 'Картофель', 'Макароны'];
    const {names, hasHistory} = recommendedProductNames(getProductUsage(), fallback);
    document.getElementById('product-recommendations-title').textContent = hasHistory ? 'Покупаете чаще' : 'Можно добавить быстро';
    document.getElementById('product-recommendations-note').textContent = hasHistory ? 'По вашей истории покупок' : 'Подборка для первого списка';
    const container = document.getElementById('product-suggestions');
    container.replaceChildren();
    names.forEach((name) => {
      const groceryItem = groceryItemByName(name);
      const defaults = catalogDefaults(name);
      const button = document.createElement('button');
      button.className = 'suggestion-chip';
      button.type = 'button';
      button.dataset.productName = name;
      button.setAttribute('aria-pressed', 'false');
      const icon = document.createElement('span');
      icon.className = 'suggestion-icon';
      icon.textContent = groceryItem?.icon || '🛒';
      const copy = document.createElement('span');
      copy.className = 'suggestion-copy';
      const label = document.createElement('strong');
      label.textContent = name;
      const detail = document.createElement('small');
      detail.textContent = `${formatQuantity(defaults.quantity)} ${defaults.unit}`;
      copy.append(label, detail);
      button.append(icon, copy);
      button.addEventListener('click', () => applyDefaults(name, true));
      container.append(button);
    });
    setSuggestionSelection(nameInput.value);
  }

  function renderCategories() {
    categoryButtons.replaceChildren();
    groceryGroups.forEach((group) => {
      const button = document.createElement('button');
      button.className = `category-button${group.id === activeGroup ? ' active' : ''}`;
      button.type = 'button';
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', String(group.id === activeGroup));
      button.innerHTML = `<span aria-hidden="true">${group.icon}</span><strong>${group.name}</strong>`;
      button.addEventListener('click', () => {
        activeGroup = group.id;
        nameInput.value = '';
        hideSearch();
        renderCategories();
        renderCatalog();
      });
      categoryButtons.append(button);
    });
    const group = groceryGroups.find((item) => item.id === activeGroup);
    selectedCategory.querySelector('strong').textContent = group ? `${group.icon} ${group.name}` : '';
  }

  function renderCatalog() {
    const normalized = nameInput.value.trim().toLocaleLowerCase('ru');
    const productUsage = getProductUsage();
    const items = groceryCatalog
      .map((item, catalogIndex) => ({item, catalogIndex, usage: Number(productUsage[item.name.toLocaleLowerCase('ru')]?.count) || 0}))
      .filter(({item}) => normalized ? item.name.toLocaleLowerCase('ru').includes(normalized) : item.group === activeGroup)
      .sort((first, second) => second.usage - first.usage || first.catalogIndex - second.catalogIndex)
      .map(({item}) => item);
    categoryButtons.classList.toggle('searching', Boolean(normalized));
    selectedCategory.querySelector('span').textContent = normalized ? `Найдено: ${items.length}` : 'Выбранная категория';
    const group = groceryGroups.find((item) => item.id === activeGroup);
    selectedCategory.querySelector('strong').textContent = normalized ? '🔎 Все категории' : `${group?.icon || ''} ${group?.name || ''}`.trim();
    catalogGrid.setAttribute('aria-label', normalized ? 'Результаты поиска товаров' : 'Товары выбранного отдела');
    catalogGrid.replaceChildren();
    items.forEach((item) => {
      const selected = normalized === item.name.toLocaleLowerCase('ru');
      const button = document.createElement('button');
      button.className = `product-catalog-option${selected ? ' selected' : ''}`;
      button.type = 'button';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', String(selected));
      const icon = document.createElement('span');
      icon.className = 'product-catalog-icon';
      icon.textContent = item.icon;
      const copy = document.createElement('span');
      copy.className = 'product-catalog-copy';
      const name = document.createElement('strong');
      name.textContent = item.name;
      const detail = document.createElement('small');
      const groupName = groceryGroups.find((catalogGroup) => catalogGroup.id === item.group)?.name || 'Другое';
      detail.textContent = normalized ? `${groupName} · ${formatQuantity(item.quantity)} ${item.unit}` : `${formatQuantity(item.quantity)} ${item.unit}`;
      copy.append(name, detail);
      const check = document.createElement('span');
      check.className = 'dish-option-check';
      check.textContent = '✓';
      button.append(icon, copy, check);
      button.addEventListener('click', () => onConfigure(item.name));
      catalogGrid.append(button);
    });
    if (items.length) return;
    const empty = document.createElement('div');
    empty.className = 'dish-options-empty';
    empty.textContent = 'Такого товара пока нет — нажмите «Добавить», чтобы создать его';
    catalogGrid.append(empty);
  }

  return {applyDefaults, renderCatalog, renderCategories, renderSuggestions, setSuggestionSelection};
}
