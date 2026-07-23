export function createShoppingItems({
  serverApi,
  getListId,
  getItems,
  setItems,
  render,
  showMessage,
  unitSteps
}) {
  async function load() {
    const listId = getListId();
    if (!listId) return;
    const items = await serverApi.getList(listId);
    setItems(items);
    const selected = serverApi.findList(listId)?.list;
    if (selected) selected.item_count = items.length;
  }

  function find(id) {
    return getItems().find((item) => item.id === id);
  }

  async function update(id, changes) {
    const item = find(id);
    if (!item) return;
    const previous = {...item};
    Object.assign(item, changes);
    render();
    try {
      await serverApi.updateItem(id, changes);
      await load();
      render();
    } catch (error) {
      Object.assign(item, previous);
      render();
      showMessage(error.message);
    }
  }

  async function adjustQuantity(id, direction) {
    const item = find(id);
    if (!item) return;
    const step = unitSteps[item.unit] || item.step || 1;
    const next = Math.max(
      step,
      Math.round((Number(item.quantity) + direction * step) * 1000) / 1000
    );
    await update(id, {quantity: next, unit: item.unit});
  }

  async function remove(id) {
    const previous = getItems();
    setItems(previous.filter((item) => item.id !== id));
    render();
    try {
      await serverApi.deleteItem(id);
    } catch (error) {
      setItems(previous);
      render();
      showMessage(error.message);
    }
  }

  return {load, find, update, adjustQuantity, remove};
}
