export function createListActions({serverApi, getListId, onChanged, showMessage}) {
  const modal = document.getElementById('list-actions-modal');
  const actionButtons = [...modal.querySelectorAll('[data-list-status]')];

  function close() {
    modal.classList.add('hidden');
  }

  function open() {
    if (!getListId()) return;
    modal.classList.remove('hidden');
  }

  async function setStatus(status) {
    const listId = getListId();
    if (!listId) return;
    actionButtons.forEach((button) => { button.disabled = true; });
    try {
      const result = await serverApi.setAllItemsStatus(listId, status);
      await onChanged();
      close();
      const message = status === 'purchased'
        ? `Отмечено купленным: ${result.updated_items}`
        : `Возвращено в покупки: ${result.updated_items}`;
      showMessage(message);
    } catch (error) {
      showMessage(error.message);
    } finally {
      actionButtons.forEach((button) => { button.disabled = false; });
    }
  }

  document.getElementById('shopping-menu').addEventListener('click', open);
  document.getElementById('close-list-actions').addEventListener('click', close);
  document.getElementById('dismiss-list-actions').addEventListener('click', close);
  actionButtons.forEach((button) => {
    button.addEventListener('click', () => setStatus(button.dataset.listStatus));
  });

  return {open, close};
}
