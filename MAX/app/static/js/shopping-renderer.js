import {categoryOrder} from './catalog.js?v=20260720-database-catalog';
import {formatQuantity} from './products.js?v=20260720-personal-catalog';

export function createShoppingRenderer({
  getItems,
  itemMarks,
  onAdjustQuantity,
  onEditItem,
  onOpenItemMenu,
  onRecordPurchase,
  onUpdateItem
}) {
  const shoppingGroups = document.getElementById('shopping-groups');
  const shoppingEmpty = document.getElementById('shopping-empty');
  const purchasedSection = document.getElementById('purchased-section');
  const purchasedList = document.getElementById('purchased-list');
  const unavailableSection = document.getElementById('unavailable-section');
  const unavailableList = document.getElementById('unavailable-list');
  let purchasedExpanded = true;
  let unavailableExpanded = true;

  function createProductRow(item) {
    const row = document.createElement('div');
    row.className = `product-row ${item.status}`;
    row.dataset.itemId = item.id;
    const mark = itemMarks[item.mark];
    if (mark) {
      row.classList.add('marked');
      row.dataset.mark = item.mark;
    }

    const check = document.createElement('button');
    check.className = 'product-check';
    check.type = 'button';
    check.setAttribute('aria-label', item.status === 'active' ? `Куплено: ${item.name}` : `Вернуть в список: ${item.name}`);
    check.innerHTML = `<svg aria-hidden="true"><use href="#${item.status === 'unavailable' ? 'unavailable' : 'check'}"/></svg>`;
    check.addEventListener('click', () => {
      if (item.status === 'active') onRecordPurchase(item.name);
      onUpdateItem(item.id, {status: item.status === 'active' ? 'purchased' : 'active'});
    });

    const copy = document.createElement('span');
    copy.className = 'product-copy';
    const title = document.createElement('strong');
    title.textContent = item.name;
    const note = document.createElement('small');
    note.textContent = item.note || item.category;
    copy.append(title, note);

    const quantity = document.createElement('div');
    quantity.className = 'quantity-control';
    const minus = document.createElement('button');
    minus.type = 'button';
    minus.setAttribute('aria-label', `Уменьшить количество: ${item.name}`);
    minus.textContent = '−';
    minus.addEventListener('click', () => onAdjustQuantity(item.id, -1));
    const value = document.createElement('button');
    value.className = 'quantity-value';
    value.type = 'button';
    value.setAttribute('aria-label', `Изменить количество: ${item.name}`);
    value.textContent = `${formatQuantity(Number(item.quantity))} ${item.unit}`;
    value.addEventListener('click', () => onEditItem(item.id));
    const plus = document.createElement('button');
    plus.type = 'button';
    plus.setAttribute('aria-label', `Увеличить количество: ${item.name}`);
    plus.textContent = '+';
    plus.addEventListener('click', () => onAdjustQuantity(item.id, 1));
    quantity.append(minus, value, plus);

    const more = document.createElement('button');
    more.className = 'product-more';
    more.type = 'button';
    more.setAttribute('aria-label', `Действия: ${item.name}${mark ? `, ${mark.label.toLocaleLowerCase('ru')} метка` : ''}`);
    more.innerHTML = '<svg aria-hidden="true"><use href="#sliders"/></svg>';
    more.addEventListener('click', () => onOpenItemMenu(item.id));

    row.append(check, copy, quantity, more);
    return row;
  }

  function renderStateSection(items, section, container, expanded) {
    section.classList.toggle('hidden', items.length === 0);
    container.classList.toggle('hidden', !expanded);
    container.replaceChildren(...items.map(createProductRow));
  }

  function render() {
    const shoppingItems = getItems();
    const activeItems = shoppingItems.filter((item) => item.status === 'active');
    const purchasedItems = shoppingItems.filter((item) => item.status === 'purchased');
    const unavailableItems = shoppingItems.filter((item) => item.status === 'unavailable');
    const total = shoppingItems.length - unavailableItems.length;
    const percent = total ? Math.round(purchasedItems.length / total * 100) : 0;

    document.getElementById('shopping-progress-text').textContent = `Куплено ${purchasedItems.length} из ${total}`;
    document.getElementById('shopping-progress-percent').textContent = `${percent}%`;
    document.getElementById('shopping-progress-bar').style.width = `${percent}%`;
    document.getElementById('purchased-count').textContent = purchasedItems.length;
    document.getElementById('unavailable-count').textContent = unavailableItems.length;

    shoppingGroups.replaceChildren();
    categoryOrder.forEach((category) => {
      const items = activeItems.filter((item) => item.category === category);
      if (!items.length) return;
      const section = document.createElement('section');
      section.className = 'product-group';
      const heading = document.createElement('h3');
      heading.textContent = category;
      const list = document.createElement('div');
      list.className = 'product-list';
      list.append(...items.map(createProductRow));
      section.append(heading, list);
      shoppingGroups.append(section);
    });

    shoppingEmpty.classList.toggle('hidden', activeItems.length > 0 || purchasedItems.length > 0 || unavailableItems.length > 0);
    renderStateSection(unavailableItems, unavailableSection, unavailableList, unavailableExpanded);
    renderStateSection(purchasedItems, purchasedSection, purchasedList, purchasedExpanded);
  }

  document.getElementById('toggle-purchased').addEventListener('click', () => {
    purchasedExpanded = !purchasedExpanded;
    render();
  });
  document.getElementById('toggle-unavailable').addEventListener('click', () => {
    unavailableExpanded = !unavailableExpanded;
    render();
  });

  return {render};
}
