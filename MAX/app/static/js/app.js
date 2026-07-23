import {categoryOrder, productCatalog, unitSteps} from './catalog.js?v=20260720-database-catalog';
import {groceryItemByName} from './grocery.js?v=20260720-database-catalog';
import {catalogDefaults, formatQuantity} from './products.js?v=20260720-personal-catalog';
import {hasPersonalizationSignals, recommendedRecipes} from './recommendations.js?v=20260720-other-category';
import {recipeCatalog, recipeGroups, scaledRecipeIngredients} from './recipes.js?v=20260720-database-catalog';
import {storageKeys, writeText} from './storage.js?v=20260721-account';
import {supplyCatalog, supplyGroups as supplyGroupCatalog} from './supplies.js?v=20260720-database-catalog';
import {initializeApp} from './app-bootstrap.js?v=20260721-mobile-keyboard';
import {createCabinet} from './cabinet.js?v=20260721-cabinet-guide';
import {createItemMenu, itemMarks} from './item-menu.js?v=20260720-database-catalog';
import {createListManager} from './list-manager.js?v=20260721-aligned-inline-add';
import {createListActions} from './list-actions.js?v=20260721-list-actions';
import {createListSharing} from './list-sharing.js?v=20260721-copy-feedback';
import {initializeOpenListRealtime} from './app-realtime.js?v=20260721-realtime3';
import {createInviteEntry} from './invite-entry.js?v=20260721-sharing';
import {createShoppingRenderer} from './shopping-renderer.js?v=20260720-database-catalog';
import {createShoppingItems} from './shopping-items.js?v=20260721-realtime';
import {createNotification} from './notifications.js?v=20260721-production-messages';
import {createProductBrowser} from './product-browser.js?v=20260720-database-catalog';
import {createUnifiedSearch} from './unified-search.js?v=20260721-products-only';
import {platformLabel} from './platform-bridge.js?v=20260721-remove-bot-button';

const serverApi = await initializeApp();
const showNotification = createNotification();
document.getElementById('profile-platform').textContent = platformLabel;
document.getElementById('send-share-list-label').textContent = `Отправить в ${platformLabel}`;
document.getElementById('send-family-invite-label').textContent = `Отправить в ${platformLabel}`;

const shoppingView = document.getElementById('shopping-view');
const itemEditorModal = document.getElementById('item-editor-modal');
const itemNameInput = document.getElementById('product-query');
const productSearchForm = document.getElementById('product-search-form');
const itemQuantityInput = document.getElementById('item-quantity');
const itemUnitSelect = document.getElementById('item-unit');
const itemCategorySelect = document.getElementById('item-category');
const itemNoteInput = document.getElementById('item-note');
const saveItemButton = document.getElementById('save-item');
const productForm = document.getElementById('product-form');
const backToProductCatalog = document.getElementById('back-to-product-catalog');
const dishForm = document.getElementById('dish-form');
const dishRecommendations = document.getElementById('dish-recommendations');
const dishCategoryButtons = document.getElementById('dish-category-buttons');
const dishSelectedCategory = document.getElementById('dish-selected-category');
const dishOptions = document.getElementById('dish-options');
const dishConfig = document.getElementById('dish-config');
const dishVariantField = document.getElementById('dish-variant-field');
const dishVariantSelect = document.getElementById('dish-variant');
const dishYieldInput = document.getElementById('dish-yield');
const dishIngredients = document.getElementById('dish-ingredients');
const supplyForm = document.getElementById('supply-form');
const supplyCategoryButtons = document.getElementById('supply-category-buttons');
const supplySelectedCategory = document.getElementById('supply-selected-category');
const supplyGroupsContainer = document.getElementById('supply-groups');
const supplyConfig = document.getElementById('supply-config');
const supplyQuantityInput = document.getElementById('supply-quantity');
const supplyUnitSelect = document.getElementById('supply-unit');
const supplyNoteInput = document.getElementById('supply-note');
let shoppingItems = [];
let editingItemId = '';
let itemKind = 'product';
let selectedRecipe = null;
let selectedRecipeVariant = '';
let excludedRecipeIngredients = new Set();
let selectedSupply = null;
let activeDishGroup = recipeGroups[0].id;
let activeSupplyGroup = supplyGroupCatalog[0].id;

function accountPersonalCatalog() {
  return Object.fromEntries(serverApi.account.personal_catalog.map((item) => [
    item.name.trim().toLocaleLowerCase('ru').replaceAll('ё', 'е'),
    {name: item.name, quantity: Number(item.quantity), unit: item.unit, category: item.category, addCount: 1}
  ]));
}

let personalCatalog = accountPersonalCatalog();
let productUsage = serverApi.account.signals.product_usage;
let recipeUsage = serverApi.account.signals.recipe_usage;

categoryOrder.forEach((category) => {
  const option = document.createElement('option');
  option.value = category;
  option.textContent = category;
  itemCategorySelect.append(option);
});

let shoppingRenderer;
let itemMenu;
let listSharing;
let listRealtime;
let shoppingItemController;
const listManager = createListManager({
  serverApi,
  showMessage: showNotification,
  onShareList: (listId) => listSharing?.open(listId),
  async onOpenShoppingList(item) {
    await shoppingItemController.load();
    shoppingRenderer.render();
    listRealtime?.watch(item.id);
  },
  onCloseShoppingList: () => listRealtime?.close()
});
const cabinet = createCabinet({serverApi, listManager, showMessage: showNotification});
createInviteEntry({serverApi, listManager, showMessage: showNotification});

shoppingItemController = createShoppingItems({
  serverApi,
  getListId: () => listManager.selectedListId,
  getItems: () => shoppingItems,
  setItems: (items) => { shoppingItems = items; },
  render: () => shoppingRenderer.render(),
  showMessage: showNotification,
  unitSteps
});

shoppingRenderer = createShoppingRenderer({
  getItems: () => shoppingItems,
  itemMarks,
  onAdjustQuantity: shoppingItemController.adjustQuantity,
  onEditItem: openItemEditor,
  onOpenItemMenu: (id) => itemMenu.open(id),
  onRecordPurchase: recordProductUsage,
  onUpdateItem: shoppingItemController.update
});

itemMenu = createItemMenu({
  findItem: shoppingItemController.find,
  itemMarks,
  onDelete: shoppingItemController.remove,
  onEdit: openItemEditor,
  onUpdate: shoppingItemController.update,
  showMessage: showNotification
});

createListActions({
  serverApi,
  getListId: () => listManager.selectedListId,
  async onChanged() {
    await shoppingItemController.load();
    shoppingRenderer.render();
  },
  showMessage: showNotification
});

listSharing = createListSharing({
  serverApi,
  getListId: () => listManager.selectedListId,
  showMessage: showNotification
});

listRealtime = initializeOpenListRealtime({
  listManager,
  shoppingView,
  loadShoppingItems: shoppingItemController.load,
  renderShopping: () => shoppingRenderer.render(),
  showMessage: showNotification
});

if (serverApi.startListId) await listManager.openListById(serverApi.startListId);
else if (serverApi.startParam === 'lists') await listManager.openAllLists();
else if (serverApi.startParam === 'cabinet') await cabinet.open();

let catalogSearch;
const productBrowser = createProductBrowser({
  getProductUsage: () => productUsage,
  hideSearch: () => catalogSearch.hide(),
  onConfigure: openProductConfiguration
});
catalogSearch = createUnifiedSearch({
  getPersonalCatalog: () => personalCatalog,
  getProductUsage: () => productUsage,
  onChoose: chooseUnifiedSearchResult,
  onCreateProduct(name) {
    setItemKind('product');
    openProductConfiguration(name);
  }
});

function chooseUnifiedSearchResult(result) {
  itemNameInput.value = '';
  itemEditorModal.classList.remove('product-config-mode');
  if (result.kind === 'supply') {
    setItemKind('supply');
    selectSupply(result.id);
  } else {
    setItemKind('product');
    openProductConfiguration(result.name, result.source === 'personal' ? result : null);
  }
}

function recordProductUsage() {}

productBrowser.renderSuggestions();

function createDishButton(recipe, className, showCategory = false) {
  const button = document.createElement('button');
  button.className = `${className}${selectedRecipe?.id === recipe.id ? ' selected' : ''}`;
  button.type = 'button';
  button.setAttribute('role', 'option');
  button.setAttribute('aria-selected', String(selectedRecipe?.id === recipe.id));
  const icon = document.createElement('span');
  icon.className = 'dish-option-icon';
  icon.textContent = recipe.icon;
  const copy = document.createElement('span');
  copy.className = 'dish-option-copy';
  const name = document.createElement('strong');
  name.textContent = recipe.name;
  const note = document.createElement('small');
  const groupName = recipeGroups.find((group) => group.id === recipe.group)?.name || 'Другое';
  const recipeDetail = `${recipe.yield.quantity} ${recipe.yield.unit} · ${recipe.variants.length > 1 ? `${recipe.variants.length} варианта` : recipe.note}`;
  note.textContent = showCategory ? `${groupName} · ${recipeDetail}` : recipeDetail;
  copy.append(name, note);
  const check = document.createElement('span');
  check.className = 'dish-option-check';
  check.textContent = '✓';
  button.append(icon, copy, check);
  button.addEventListener('click', () => selectRecipe(recipe.id));
  return button;
}

function renderDishRecommendations() {
  const hasPersonalHistory = hasPersonalizationSignals(productUsage, recipeUsage);
  document.getElementById('dish-recommendations-note').textContent = hasPersonalHistory ? 'На основе ваших покупок' : 'Подборка для начала';
  const recipes = recommendedRecipes(recipeCatalog, productUsage, recipeUsage).slice(0, 10);
  dishRecommendations.replaceChildren(...recipes.map((recipe) => createDishButton(recipe, 'dish-recommendation')));
}

function renderDishCategoryTabs() {
  dishCategoryButtons.replaceChildren();
  recipeGroups.forEach((group) => {
    const button = document.createElement('button');
    button.className = `category-button${group.id === activeDishGroup ? ' active' : ''}`;
    button.type = 'button';
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-selected', String(group.id === activeDishGroup));
    button.innerHTML = `<span aria-hidden="true">${group.icon}</span><strong>${group.name}</strong>`;
    button.addEventListener('click', () => {
      activeDishGroup = group.id;
      itemNameInput.value = '';
      catalogSearch.hide();
      renderDishCategoryTabs();
      renderDishOptions();
    });
    dishCategoryButtons.append(button);
  });
  const selectedGroup = recipeGroups.find((group) => group.id === activeDishGroup);
  dishSelectedCategory.querySelector('strong').textContent = selectedGroup ? `${selectedGroup.icon} ${selectedGroup.name}` : '';
}

function renderDishOptions(query = '') {
  const normalized = query.trim().toLocaleLowerCase('ru');
  const recipes = recommendedRecipes(recipeCatalog, productUsage, recipeUsage, normalized)
    .filter((recipe) => normalized || recipe.group === activeDishGroup);
  dishCategoryButtons.classList.toggle('searching', Boolean(normalized));
  dishSelectedCategory.querySelector('span').textContent = normalized ? `Найдено: ${recipes.length}` : 'Выбранная категория';
  dishSelectedCategory.querySelector('strong').textContent = normalized
    ? '🔎 Все категории'
    : `${recipeGroups.find((group) => group.id === activeDishGroup)?.icon || ''} ${recipeGroups.find((group) => group.id === activeDishGroup)?.name || ''}`.trim();
  dishOptions.setAttribute('aria-label', normalized ? 'Результаты поиска блюд' : 'Блюда выбранной категории');
  dishOptions.replaceChildren();
  dishOptions.append(...recipes.map((recipe) => createDishButton(recipe, 'dish-option', Boolean(normalized))));
  if (!recipes.length) {
    const empty = document.createElement('div');
    empty.className = 'dish-options-empty';
    empty.textContent = 'Такого блюда пока нет в каталоге';
    dishOptions.append(empty);
  }
}

function selectedRecipeIngredients() {
  if (!selectedRecipe) return [];
  return scaledRecipeIngredients(selectedRecipe, selectedRecipeVariant, Number(dishYieldInput.value));
}

function renderDishIngredients() {
  const ingredients = selectedRecipeIngredients();
  dishIngredients.replaceChildren();
  ingredients.forEach((ingredient) => {
    const row = document.createElement('label');
    row.className = 'dish-ingredient';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = !excludedRecipeIngredients.has(ingredient.name);
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) excludedRecipeIngredients.delete(ingredient.name);
      else excludedRecipeIngredients.add(ingredient.name);
      renderDishIngredients();
    });
    const mark = document.createElement('span');
    mark.className = 'dish-ingredient-check';
    mark.textContent = '✓';
    const name = document.createElement('span');
    name.className = 'dish-ingredient-name';
    name.textContent = ingredient.name;
    const quantity = document.createElement('strong');
    quantity.textContent = `${formatQuantity(ingredient.quantity)} ${ingredient.unit}`;
    row.append(checkbox, mark, name, quantity);
    dishIngredients.append(row);
  });
  const selectedCount = ingredients.filter((ingredient) => !excludedRecipeIngredients.has(ingredient.name)).length;
  document.getElementById('dish-ingredients-count').textContent = `${selectedCount} из ${ingredients.length}`;
  saveItemButton.disabled = selectedCount === 0;
}

function renderDishConfig() {
  if (!selectedRecipe) {
    dishConfig.classList.add('hidden');
    saveItemButton.disabled = true;
    return;
  }
  dishConfig.classList.remove('hidden');
  document.getElementById('dish-selected-icon').textContent = selectedRecipe.icon;
  document.getElementById('dish-selected-name').textContent = selectedRecipe.name;
  document.getElementById('dish-selected-note').textContent = selectedRecipe.note;
  document.getElementById('dish-yield-label').textContent = selectedRecipe.yield.label;
  document.getElementById('dish-yield-unit').textContent = selectedRecipe.yield.unit;
  dishYieldInput.min = selectedRecipe.yield.step;
  dishYieldInput.step = selectedRecipe.yield.step;
  dishVariantSelect.replaceChildren();
  selectedRecipe.variants.forEach((variant) => {
    const option = document.createElement('option');
    option.value = variant.id;
    option.textContent = variant.name;
    option.selected = variant.id === selectedRecipeVariant;
    dishVariantSelect.append(option);
  });
  dishVariantField.classList.toggle('hidden', selectedRecipe.variants.length === 1);
  renderDishIngredients();
}

function selectRecipe(recipeId) {
  selectedRecipe = recipeCatalog.find((recipe) => recipe.id === recipeId) || null;
  if (selectedRecipe) activeDishGroup = selectedRecipe.group;
  selectedRecipeVariant = selectedRecipe?.variants[0]?.id || '';
  excludedRecipeIngredients = new Set();
  if (selectedRecipe) dishYieldInput.value = selectedRecipe.yield.quantity;
  renderDishRecommendations();
  renderDishCategoryTabs();
  renderDishOptions();
  renderDishConfig();
  dishConfig.scrollIntoView({block: 'nearest', behavior: 'smooth'});
}

function renderSupplyCategoryTabs() {
  supplyCategoryButtons.replaceChildren();
  supplyGroupCatalog.forEach((group) => {
    const button = document.createElement('button');
    button.className = `category-button${group.id === activeSupplyGroup ? ' active' : ''}`;
    button.type = 'button';
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-selected', String(group.id === activeSupplyGroup));
    button.innerHTML = `<span aria-hidden="true">${group.icon}</span><strong>${group.name}</strong>`;
    button.addEventListener('click', () => {
      activeSupplyGroup = group.id;
      itemNameInput.value = '';
      catalogSearch.hide();
      renderSupplyCategoryTabs();
      renderSupplyOptions();
    });
    supplyCategoryButtons.append(button);
  });
  const selectedGroup = supplyGroupCatalog.find((group) => group.id === activeSupplyGroup);
  supplySelectedCategory.querySelector('strong').textContent = selectedGroup ? `${selectedGroup.icon} ${selectedGroup.name}` : '';
}

function renderSupplyOptions(query = '') {
  const normalized = query.trim().toLocaleLowerCase('ru');
  supplyGroupsContainer.replaceChildren();
  const items = supplyCatalog
    .map((item, catalogIndex) => ({item, catalogIndex, usage: Number(productUsage[item.name.toLocaleLowerCase('ru')]?.count) || 0}))
    .filter(({item}) => (normalized || item.group === activeSupplyGroup) && item.name.toLocaleLowerCase('ru').includes(normalized))
    .sort((first, second) => second.usage - first.usage || first.catalogIndex - second.catalogIndex)
    .map(({item}) => item);
  supplyCategoryButtons.classList.toggle('searching', Boolean(normalized));
  supplySelectedCategory.querySelector('span').textContent = normalized ? `Найдено: ${items.length}` : 'Выбранная категория';
  supplySelectedCategory.querySelector('strong').textContent = normalized
    ? '🔎 Все категории'
    : `${supplyGroupCatalog.find((group) => group.id === activeSupplyGroup)?.icon || ''} ${supplyGroupCatalog.find((group) => group.id === activeSupplyGroup)?.name || ''}`.trim();
  supplyGroupsContainer.setAttribute('aria-label', normalized ? 'Результаты поиска товаров для дома' : 'Товары выбранной категории');
  items.forEach((item) => {
      const button = document.createElement('button');
      button.className = `supply-option${selectedSupply?.id === item.id ? ' selected' : ''}`;
      button.type = 'button';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', String(selectedSupply?.id === item.id));
      const itemIcon = document.createElement('span');
      itemIcon.className = 'supply-option-icon';
      itemIcon.textContent = item.icon;
      const copy = document.createElement('span');
      copy.className = 'supply-option-copy';
      const title = document.createElement('strong');
      title.textContent = item.name;
      const note = document.createElement('small');
      const groupName = supplyGroupCatalog.find((group) => group.id === item.group)?.name || 'Другое';
      note.textContent = normalized ? `${groupName} · ${item.note}` : item.note;
      copy.append(title, note);
      const check = document.createElement('span');
      check.className = 'dish-option-check';
      check.textContent = '✓';
      button.append(itemIcon, copy, check);
      button.addEventListener('click', () => selectSupply(item.id));
      supplyGroupsContainer.append(button);
  });
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'dish-options-empty';
    empty.textContent = 'Такой принадлежности пока нет в каталоге';
    supplyGroupsContainer.append(empty);
  }
}

function renderSupplyConfig() {
  if (!selectedSupply) {
    supplyConfig.classList.add('hidden');
    saveItemButton.disabled = true;
    return;
  }
  const defaults = catalogDefaults(selectedSupply.name);
  supplyConfig.classList.remove('hidden');
  document.getElementById('supply-selected-icon').textContent = selectedSupply.icon;
  document.getElementById('supply-selected-name').textContent = selectedSupply.name;
  document.getElementById('supply-selected-note').textContent = selectedSupply.note;
  document.getElementById('supply-category').textContent = defaults.category;
  saveItemButton.disabled = false;
}

function selectSupply(supplyId) {
  selectedSupply = supplyCatalog.find((item) => item.id === supplyId) || null;
  if (selectedSupply) {
    activeSupplyGroup = selectedSupply.group;
    const defaults = catalogDefaults(selectedSupply.name);
    supplyQuantityInput.value = defaults.quantity;
    supplyQuantityInput.min = unitSteps[defaults.unit] || 1;
    supplyQuantityInput.step = unitSteps[defaults.unit] || 1;
    supplyUnitSelect.value = defaults.unit;
    supplyNoteInput.value = '';
  }
  renderSupplyCategoryTabs();
  renderSupplyOptions();
  renderSupplyConfig();
  supplyConfig.scrollIntoView({block: 'nearest', behavior: 'smooth'});
}

function setItemKind(kind) {
  itemKind = !editingItemId && ['product', 'dish', 'supply'].includes(kind) ? kind : 'product';
  if (itemKind !== 'product') {
    productForm.classList.remove('config-mode');
    backToProductCatalog.classList.add('hidden');
    itemEditorModal.classList.remove('product-config-mode');
  }
  document.querySelectorAll('[data-item-kind]').forEach((button) => {
    const selected = button.dataset.itemKind === itemKind;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-selected', String(selected));
  });
  productForm.classList.toggle('hidden', itemKind !== 'product');
  dishForm.classList.toggle('hidden', itemKind !== 'dish');
  supplyForm.classList.toggle('hidden', itemKind !== 'supply');
  if (itemKind === 'dish') {
    document.getElementById('item-editor-title').textContent = 'Добавить блюдо';
    document.getElementById('item-editor-description').textContent = 'Выберите блюдо — продукты и их количество рассчитаются автоматически.';
    saveItemButton.textContent = 'Добавить ингредиенты';
    saveItemButton.disabled = !selectedRecipe;
    renderDishRecommendations();
    renderDishCategoryTabs();
    renderDishOptions();
    renderDishConfig();
  } else if (itemKind === 'supply') {
    document.getElementById('item-editor-title').textContent = 'Добавить для дома';
    document.getElementById('item-editor-description').textContent = 'Выберите нужное для дома, гигиены или отдыха.';
    saveItemButton.textContent = 'Добавить в список';
    saveItemButton.disabled = !selectedSupply;
    renderSupplyCategoryTabs();
    renderSupplyOptions();
    renderSupplyConfig();
  } else {
    const item = editingItemId ? shoppingItemController.find(editingItemId) : null;
    document.getElementById('item-editor-title').textContent = item ? 'Изменить товар' : 'Добавить в список';
    document.getElementById('item-editor-description').textContent = item ? 'Измените количество, единицу, отдел или примечание.' : 'Найдите товар, блюдо или нужное для дома — либо выберите категорию.';
    saveItemButton.textContent = item ? 'Сохранить изменения' : 'Добавить';
    saveItemButton.disabled = false;
  }
}

function openProductConfiguration(name, personalDefaults = null) {
  productBrowser.applyDefaults(name);
  if (personalDefaults) {
    itemQuantityInput.value = personalDefaults.quantity;
    itemUnitSelect.value = personalDefaults.unit;
    itemCategorySelect.value = personalDefaults.category;
    itemQuantityInput.step = unitSteps[personalDefaults.unit] || 1;
  }
  productForm.classList.add('config-mode');
  itemEditorModal.classList.add('product-config-mode');
  backToProductCatalog.classList.remove('hidden');
  document.getElementById('item-editor-title').textContent = name;
  document.getElementById('item-editor-description').textContent = 'Укажите количество, единицу и отдел магазина.';
  saveItemButton.textContent = 'Добавить в список';
  document.querySelector('.item-editor-card').scrollTo({top: 0, behavior: 'smooth'});
  window.setTimeout(() => itemQuantityInput.focus(), 120);
}

function showProductCatalog() {
  productForm.classList.remove('config-mode');
  itemEditorModal.classList.remove('product-config-mode');
  backToProductCatalog.classList.add('hidden');
  itemNameInput.value = '';
  catalogSearch.hide();
  productBrowser.renderCategories();
  productBrowser.renderCatalog();
  document.getElementById('item-editor-title').textContent = 'Добавить в список';
  document.getElementById('item-editor-description').textContent = 'Найдите товар, блюдо или нужное для дома — либо выберите категорию.';
  saveItemButton.textContent = 'Добавить';
  document.querySelector('.item-editor-card').scrollTo({top: 0, behavior: 'smooth'});
}

async function addSelectedSupplyToList() {
  if (!selectedSupply) return;
  const unit = supplyUnitSelect.value;
  const minimum = unitSteps[unit] || 1;
  const quantity = Number(supplyQuantityInput.value);
  if (!Number.isFinite(quantity) || quantity < minimum) {
    supplyQuantityInput.value = minimum;
    supplyQuantityInput.focus();
    return;
  }
  const defaults = catalogDefaults(selectedSupply.name);
  const values = {
    name: selectedSupply.name,
    category: defaults.category,
    quantity,
    unit,
    note: supplyNoteInput.value.trim()
  };
  const supplyName = selectedSupply.name;
  try {
    await serverApi.addItem(listManager.selectedListId, values);
    await shoppingItemController.load();
    shoppingRenderer.render();
    itemEditorModal.classList.add('hidden');
    showNotification(`Добавлено: ${supplyName}`);
  } catch (error) {
    showNotification(error.message);
  }
}

async function addSelectedRecipeToList() {
  if (!selectedRecipe) return;
  const ingredients = selectedRecipeIngredients().filter((ingredient) => !excludedRecipeIngredients.has(ingredient.name));
  if (!ingredients.length) return;
  const recipeName = selectedRecipe.name;
  const excludedProductIds = selectedRecipeIngredients()
    .filter((ingredient) => excludedRecipeIngredients.has(ingredient.name))
    .map((ingredient) => ingredient.productId)
    .filter(Boolean);
  try {
    await serverApi.addRecipe(
      listManager.selectedListId,
      selectedRecipe,
      Number(dishYieldInput.value),
      selectedRecipeVariant,
      excludedProductIds
    );
    await shoppingItemController.load();
    await serverApi.refreshAccount();
    recipeUsage = serverApi.account.signals.recipe_usage;
    shoppingRenderer.render();
    itemEditorModal.classList.add('hidden');
    showNotification(`${recipeName}: добавлено ${ingredients.length} продуктов`);
  } catch (error) {
    showNotification(error.message);
  }
}

function openItemEditor(id = '') {
  editingItemId = id;
  const item = id ? shoppingItemController.find(id) : null;
  document.getElementById('item-kind-dish').disabled = Boolean(item);
  document.getElementById('item-kind-supply').disabled = Boolean(item);
  itemNameInput.value = item?.name || '';
  itemQuantityInput.value = item?.quantity || 1;
  itemUnitSelect.value = item?.unit || 'шт.';
  itemCategorySelect.value = item?.category || 'Другое';
  itemNoteInput.value = item?.note || '';
  itemQuantityInput.step = unitSteps[item?.unit || 'шт.'];
  selectedRecipe = null;
  selectedRecipeVariant = '';
  excludedRecipeIngredients = new Set();
  dishConfig.classList.add('hidden');
  selectedSupply = null;
  supplyConfig.classList.add('hidden');
  catalogSearch.hide();
  productForm.classList.remove('config-mode');
  itemEditorModal.classList.remove('product-config-mode');
  backToProductCatalog.classList.add('hidden');
  productBrowser.renderSuggestions();
  productBrowser.renderCategories();
  productBrowser.renderCatalog();
  setItemKind('product');
  if (item) {
    productForm.classList.add('config-mode');
    itemEditorModal.classList.add('product-config-mode');
  }
  itemEditorModal.classList.remove('hidden');
  itemNameInput.focus();
}

document.getElementById('add-product').addEventListener('click', () => openItemEditor());
document.getElementById('close-item-editor').addEventListener('click', () => {
  catalogSearch.hide();
  itemEditorModal.classList.remove('product-config-mode');
  itemEditorModal.classList.add('hidden');
});
backToProductCatalog.addEventListener('click', showProductCatalog);
document.querySelectorAll('[data-item-kind]').forEach((button) => button.addEventListener('click', () => {
  if (button.dataset.itemKind !== itemKind) {
    itemNameInput.value = '';
    catalogSearch.hide();
  }
  setItemKind(button.dataset.itemKind);
}));
supplyUnitSelect.addEventListener('change', () => {
  const minimum = unitSteps[supplyUnitSelect.value] || 1;
  supplyQuantityInput.min = minimum;
  supplyQuantityInput.step = minimum;
  if (!Number(supplyQuantityInput.value) || Number(supplyQuantityInput.value) < minimum) supplyQuantityInput.value = minimum;
});
dishVariantSelect.addEventListener('change', () => {
  selectedRecipeVariant = dishVariantSelect.value;
  excludedRecipeIngredients = new Set();
  renderDishIngredients();
});
function adjustDishYield(direction) {
  if (!selectedRecipe) return;
  const step = selectedRecipe.yield.step;
  const next = Math.max(step, Math.round((Number(dishYieldInput.value || step) + direction * step) * 100) / 100);
  dishYieldInput.value = next;
  renderDishIngredients();
}
document.getElementById('dish-yield-minus').addEventListener('click', () => adjustDishYield(-1));
document.getElementById('dish-yield-plus').addEventListener('click', () => adjustDishYield(1));
dishYieldInput.addEventListener('change', () => {
  if (!selectedRecipe) return;
  const minimum = selectedRecipe.yield.step;
  const value = Number(dishYieldInput.value);
  dishYieldInput.value = Number.isFinite(value) && value >= minimum ? value : minimum;
  renderDishIngredients();
});
itemUnitSelect.addEventListener('change', () => {
  itemQuantityInput.step = unitSteps[itemUnitSelect.value];
  const minimum = unitSteps[itemUnitSelect.value];
  if (!Number(itemQuantityInput.value) || Number(itemQuantityInput.value) < minimum) itemQuantityInput.value = minimum;
});
itemNameInput.addEventListener('change', () => {
  const name = itemNameInput.value.trim();
  if (!editingItemId && (productCatalog[name.toLocaleLowerCase('ru')] || groceryItemByName(name))) productBrowser.applyDefaults(name);
});
itemNameInput.addEventListener('input', () => {
  catalogSearch.render(itemNameInput.value);
  productBrowser.setSuggestionSelection(itemNameInput.value);
  if (itemKind === 'product') productBrowser.renderCatalog();
});
itemNameInput.addEventListener('focus', () => catalogSearch.render(itemNameInput.value));
productSearchForm.addEventListener('submit', (event) => {
  event.preventDefault();
  catalogSearch.activate(itemNameInput.value);
});
itemNameInput.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    catalogSearch.hide();
    return;
  }
  if (event.key === 'Enter' && itemNameInput.value.trim()) {
    event.preventDefault();
    catalogSearch.activate(itemNameInput.value);
  }
});
document.addEventListener('click', (event) => {
  if (!event.target.closest('.name-field')) catalogSearch.hide();
});
saveItemButton.addEventListener('click', async () => {
  if (itemKind === 'dish') {
    await addSelectedRecipeToList();
    return;
  }
  if (itemKind === 'supply') {
    await addSelectedSupplyToList();
    return;
  }
  const name = itemNameInput.value.trim();
  if (!editingItemId && !productForm.classList.contains('config-mode')) {
    if (!name) {
      itemNameInput.focus();
      return;
    }
    catalogSearch.activate(name);
    return;
  }
  const unit = itemUnitSelect.value;
  const minimum = unitSteps[unit];
  const quantity = Number(itemQuantityInput.value);
  if (!name) {
    itemNameInput.focus();
    return;
  }
  if (!Number.isFinite(quantity) || quantity < minimum) {
    itemQuantityInput.value = minimum;
    itemQuantityInput.focus();
    return;
  }
  const values = {
    productId: catalogDefaults(name).productId,
    name,
    quantity,
    unit,
    step: minimum,
    category: itemCategorySelect.value,
    note: itemNoteInput.value.trim()
  };
  saveItemButton.disabled = true;
  try {
    if (editingItemId) await serverApi.updateItem(editingItemId, values);
    else await serverApi.addItem(listManager.selectedListId, values);
    await shoppingItemController.load();
    if (!values.productId) {
      await serverApi.refreshAccount();
      personalCatalog = accountPersonalCatalog();
    }
    shoppingRenderer.render();
    catalogSearch.hide();
    itemEditorModal.classList.add('hidden');
    showNotification(editingItemId ? `Изменено: ${name}` : `Добавлено: ${name}`);
  } catch (error) {
    showNotification(error.message);
  } finally {
    saveItemButton.disabled = false;
  }
});
