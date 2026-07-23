import {formatQuantity} from './products.js?v=20260720-personal-catalog';

export const itemMarks = Object.freeze({
  blue: {label: 'Синяя'},
  amber: {label: 'Жёлтая'},
  violet: {label: 'Лиловая'},
  coral: {label: 'Коралловая'}
});

export function createItemMenu({findItem, itemMarks, onDelete, onEdit, onUpdate, showMessage}) {
  const menuModal = document.getElementById('item-menu-modal');
  const deleteModal = document.getElementById('delete-item-modal');
  let activeItemId = '';

  function close() {
    menuModal.classList.add('hidden');
  }

  function open(id) {
    activeItemId = id;
    const item = findItem(id);
    if (!item) return;
    document.getElementById('item-menu-title').textContent = item.name;
    document.getElementById('item-menu-description').textContent = `${formatQuantity(Number(item.quantity))} ${item.unit} · ${item.category}`;
    document.getElementById('unavailable-item-title').textContent = item.status === 'unavailable' ? 'Вернуть в список' : 'Нет в наличии';
    document.getElementById('unavailable-item-hint').textContent = item.status === 'unavailable'
      ? 'Товар снова появится среди активных покупок'
      : 'Перенесём в отдельный раздел списка';
    const clearMarkButton = document.querySelector('[data-item-mark=""]');
    clearMarkButton.querySelector('.item-mark-clear-label').textContent = item.mark ? 'Снять метку' : 'Без метки';
    document.querySelectorAll('[data-item-mark]').forEach((button) => {
      const selected = button.dataset.itemMark === (item.mark || '');
      button.classList.toggle('selected', selected);
      button.setAttribute('aria-checked', String(selected));
    });
    menuModal.classList.remove('hidden');
  }

  document.getElementById('close-item-menu').addEventListener('click', close);
  document.getElementById('edit-item').addEventListener('click', () => {
    close();
    onEdit(activeItemId);
  });
  document.querySelectorAll('[data-item-mark]').forEach((button) => button.addEventListener('click', () => {
    const item = findItem(activeItemId);
    if (!item) return;
    const mark = button.dataset.itemMark;
    onUpdate(item.id, {mark});
    close();
    showMessage(mark ? `${itemMarks[mark].label} метка: ${item.name}` : `Метка снята: ${item.name}`);
  }));
  document.getElementById('unavailable-item').addEventListener('click', () => {
    const item = findItem(activeItemId);
    if (item) onUpdate(item.id, {status: item.status === 'unavailable' ? 'active' : 'unavailable'});
    close();
  });
  document.getElementById('request-delete-item').addEventListener('click', () => {
    const item = findItem(activeItemId);
    if (!item) return;
    document.getElementById('delete-item-description').textContent = `«${item.name}» будет удалён из списка.`;
    close();
    deleteModal.classList.remove('hidden');
  });
  document.getElementById('cancel-delete-item').addEventListener('click', () => deleteModal.classList.add('hidden'));
  document.getElementById('confirm-delete-item').addEventListener('click', () => {
    const item = findItem(activeItemId);
    onDelete(activeItemId);
    deleteModal.classList.add('hidden');
    if (item) showMessage(`Удалено: ${item.name}`);
  });

  return {open};
}
