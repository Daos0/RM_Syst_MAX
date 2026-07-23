import {createListRealtime} from './list-realtime.js?v=20260721-realtime3';

export function initializeOpenListRealtime({
  listManager,
  shoppingView,
  loadShoppingItems,
  renderShopping,
  showMessage
}) {
  return createListRealtime({
    async onChanged(listId) {
      if (listManager.selectedListId !== listId || shoppingView.classList.contains('hidden')) return;
      await loadShoppingItems();
      renderShopping();
    },
    async onAccessLost() {
      showMessage('Этот совместный список больше вам недоступен');
      await listManager.openAllLists();
    }
  });
}
