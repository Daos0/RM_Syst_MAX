import {readText, storageKeys, writeText} from './storage.js?v=20260721-account';
import {formatProductCount} from './formatters.js?v=20260721-account';

export function createListManager({serverApi, onOpenShoppingList, onCloseShoppingList, onShareList, showMessage}) {
  const app = document.querySelector('.app');
  const homeView = document.getElementById('home-view');
  const listsView = document.getElementById('lists-view');
  const shoppingView = document.getElementById('shopping-view');
  const listsKicker = document.getElementById('lists-kicker');
  const listsTitle = document.getElementById('lists-title');
  const listOptions = document.getElementById('list-options');
  const openManagerButton = document.getElementById('open-list-manager');
  const managerModal = document.getElementById('list-manager-modal');
  const managerList = document.getElementById('manager-list');
  const managerAddButton = document.getElementById('manager-add-list');
  const managerAddGoals = document.getElementById('manager-add-goals');
  const customModal = document.getElementById('custom-list-modal');
  const customName = document.getElementById('custom-list-name');
  const customModalTitle = document.getElementById('custom-list-title');
  const customModalDescription = document.getElementById('custom-list-description');
  const saveCustomButton = document.getElementById('save-custom-list');
  const removalModal = document.getElementById('list-removal-modal');
  const removalTitle = document.getElementById('list-removal-title');
  const removalDescription = document.getElementById('list-removal-description');
  const confirmRemovalButton = document.getElementById('confirm-list-removal');

  let currentGoal = readText(storageKeys.goal, 'Для себя');
  let selectedList = null;
  let editingListId = '';
  let editingGoal = currentGoal;
  let listScope = 'goal';
  let pendingListRemoval = null;

  const goalByKind = Object.freeze({
    personal: 'Для себя',
    family: 'Для семьи',
    shared: 'Совместно'
  });
  const priorityKinds = Object.freeze(['shared', 'family', 'personal']);

  function currentLists() {
    return serverApi.listsForGoal(currentGoal);
  }

  function setActiveGoal(goal) {
    currentGoal = goal;
    writeText(storageKeys.goal, goal);
    document.querySelectorAll('[data-goal]').forEach((item) => {
      item.classList.toggle('active', item.dataset.goal === goal);
    });
  }

  function setNavigation(active) {
    document.querySelectorAll('[data-nav]').forEach((button) => {
      const isActive = button.dataset.nav === active;
      button.classList.toggle('active', isActive);
      if (isActive) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
  }

  function listNote(item) {
    const count = Number(item.item_count) || 0;
    if (!count) return 'Пустой список';
    return formatProductCount(count);
  }

  async function openShoppingList(item, goal = currentGoal) {
    setActiveGoal(goal);
    selectedList = item;
    document.getElementById('shopping-title').textContent = item.title;
    document.getElementById('shopping-goal').textContent = currentGoal;
    const selectedSpace = serverApi.findList(item.id)?.space;
    document.getElementById('shopping-share').classList.toggle(
      'hidden', currentGoal !== 'Совместно' || selectedSpace?.role !== 'owner'
    );
    homeView.classList.add('hidden');
    listsView.classList.add('hidden');
    shoppingView.classList.remove('hidden');
    app.classList.add('selection-mode');
    app.classList.add('shopping-mode');
    app.classList.remove('list-goal-mode', 'list-all-mode');
    setNavigation('lists');
    await onOpenShoppingList(item);
    window.scrollTo({top: 0, behavior: 'auto'});
  }

  async function togglePin(item) {
    const pinned = !item.is_pinned;
    try {
      await serverApi.setListPinned(item.id, pinned);
      renderListOptions();
      showMessage(pinned ? `Закреплено наверху: ${item.title}` : `Откреплено: ${item.title}`);
    } catch (error) {
      showMessage(error.message);
    }
  }

  function makeListOption(item, number, goal = currentGoal, options = {}) {
    const row = document.createElement('div');
    row.className = `list-option${item.is_pinned ? ' pinned' : ''}`;
    const button = document.createElement('button');
    button.className = 'list-option-open';
    button.type = 'button';
    const icon = document.createElement('span');
    icon.className = 'list-option-icon';
    icon.textContent = number;
    const copy = document.createElement('span');
    copy.className = 'list-option-copy';
    const title = document.createElement('strong');
    title.textContent = item.title;
    const subtitle = document.createElement('small');
    subtitle.textContent = options.showGoal ? `${goal} · ${listNote(item)}` : listNote(item);
    copy.append(title, subtitle);
    button.append(icon, copy);
    button.addEventListener('click', () => openShoppingList(item, goal));
    row.append(button);
    const actions = document.createElement('span');
    actions.className = 'list-option-actions';
    if (options.showPin) {
      const pin = document.createElement('button');
      pin.className = `list-option-pin${item.is_pinned ? ' active' : ''}`;
      pin.type = 'button';
      pin.setAttribute('aria-label', `${item.is_pinned ? 'Открепить' : 'Закрепить'}: ${item.title}`);
      pin.setAttribute('aria-pressed', String(Boolean(item.is_pinned)));
      pin.innerHTML = '<svg aria-hidden="true"><use href="#pin"/></svg>';
      pin.addEventListener('click', () => togglePin(item));
      actions.append(pin);
    }
    const space = serverApi.findList(item.id)?.space;
    if (goal === 'Совместно' && space?.role === 'owner') {
      const share = document.createElement('button');
      share.className = 'list-option-share';
      share.type = 'button';
      share.setAttribute('aria-label', `Поделиться: ${item.title}`);
      share.innerHTML = '<svg aria-hidden="true"><use href="#share"/></svg>';
      share.addEventListener('click', () => onShareList(item.id));
      actions.append(share);
    }
    if (actions.childElementCount) row.append(actions);
    return row;
  }

  function appendEmptyState(message) {
    const empty = document.createElement('div');
    empty.className = 'shopping-empty';
    empty.innerHTML = `<strong>Списков пока нет</strong><small>${message}</small>`;
    listOptions.append(empty);
  }

  function openManager() {
    renderManager();
    managerModal.classList.remove('hidden');
  }

  function makeInlineAddButton() {
    const button = document.createElement('button');
    button.className = 'inline-list-add';
    button.type = 'button';
    button.innerHTML = '<span><svg aria-hidden="true"><use href="#plus"/></svg></span><strong>Добавить список</strong>';
    button.addEventListener('click', openManager);
    return button;
  }

  function allListEntries() {
    return priorityKinds.flatMap((kind) => {
      const goal = goalByKind[kind];
      return serverApi.account.spaces
        .filter((space) => space.kind === kind)
        .flatMap((space) => space.lists.map((item) => ({item, goal, kind})));
    });
  }

  function appendAllListsHeading(label, count, pinned = false) {
    const heading = document.createElement('div');
    heading.className = `all-lists-heading${pinned ? ' pinned' : ''}`;
    const title = document.createElement('strong');
    title.textContent = label;
    const total = document.createElement('small');
    total.textContent = count;
    heading.append(title, total);
    listOptions.append(heading);
  }

  function renderAllListOptions() {
    const entries = allListEntries();
    let number = 1;
    const pinned = entries.filter(({item}) => item.is_pinned);
    if (pinned.length) {
      appendAllListsHeading('Закреплённые', pinned.length, true);
      pinned.forEach(({item, goal}) => {
        listOptions.append(makeListOption(item, number, goal, {showPin: true, showGoal: true}));
        number += 1;
      });
    }
    priorityKinds.forEach((kind) => {
      const goal = goalByKind[kind];
      const visible = entries.filter((entry) => entry.kind === kind && !entry.item.is_pinned);
      if (!visible.length) return;
      appendAllListsHeading(goal, visible.length);
      visible.forEach(({item}) => {
        listOptions.append(makeListOption(item, number, goal, {showPin: true}));
        number += 1;
      });
    });
    if (number === 1) appendEmptyState('Создайте первый список на главной странице.');
  }

  function renderListOptions() {
    selectedList = null;
    listOptions.replaceChildren();
    if (listScope === 'all') {
      listOptions.classList.remove('sparse');
      renderAllListOptions();
      return;
    }
    const lists = currentLists();
    listOptions.classList.toggle('sparse', lists.length <= 2);
    lists.forEach((item, index) => listOptions.append(makeListOption(item, index + 1)));
    if (!lists.length) {
      appendEmptyState('Нажмите «Добавить / изменить», чтобы создать первый.');
    }
    if (lists.length < 5) listOptions.append(makeInlineAddButton());
  }

  function makeManagerButton(label, iconName, className, handler) {
    const button = document.createElement('button');
    button.className = `manager-icon-button${className ? ` ${className}` : ''}`;
    button.type = 'button';
    button.setAttribute('aria-label', label);
    button.innerHTML = `<svg aria-hidden="true"><use href="#${iconName}"/></svg>`;
    button.addEventListener('click', handler);
    return button;
  }

  function openListEditor(item = null, goal = currentGoal) {
    editingListId = item?.id || '';
    editingGoal = goal;
    customModalTitle.textContent = item ? 'Редактировать список' : 'Добавить список';
    customModalDescription.textContent = item ? 'Измените название выбранного списка.' : 'Введите название нового списка.';
    saveCustomButton.textContent = item ? 'Сохранить изменения' : 'Добавить';
    customName.value = item?.title || '';
    customModal.classList.remove('hidden');
    customName.focus();
  }

  async function deleteList(item, goal) {
    try {
      await serverApi.deleteList(item.id);
      renderListOptions();
      renderManager();
      showMessage(goal === 'Совместно' ? `Убрано у вас: ${item.title}` : `Удалено: ${item.title}`);
    } catch (error) {
      showMessage(error.message);
    }
  }

  function requestListRemoval(item, goal) {
    pendingListRemoval = {item, goal};
    if (goal === 'Совместно') {
      removalTitle.textContent = 'Убрать совместный список у себя?';
      removalDescription.textContent = 'Список исчезнет у вас. У присоединившихся участников он сохранится; если участников нет, список удалится полностью.';
      confirmRemovalButton.textContent = 'Убрать у себя';
    } else if (goal === 'Для семьи') {
      removalTitle.textContent = 'Удалить семейный список?';
      removalDescription.textContent = 'Список и все его товары исчезнут у каждого участника семьи.';
      confirmRemovalButton.textContent = 'Удалить у всех';
    } else {
      removalTitle.textContent = 'Удалить личный список?';
      removalDescription.textContent = 'Список и все его товары будут удалены.';
      confirmRemovalButton.textContent = 'Удалить';
    }
    removalModal.classList.remove('hidden');
  }

  function managerEntries() {
    const goals = listScope === 'all' ? priorityKinds.map((kind) => goalByKind[kind]) : [currentGoal];
    return goals.flatMap((goal) => serverApi.listsForGoal(goal).map((item) => ({
      item,
      goal,
      isOwner: serverApi.findList(item.id)?.space.role === 'owner'
    })));
  }

  function appendManagerHeading(goal, count) {
    const heading = document.createElement('div');
    heading.className = 'manager-section-heading';
    const title = document.createElement('strong');
    title.textContent = goal;
    const total = document.createElement('small');
    total.textContent = count;
    heading.append(title, total);
    managerList.append(heading);
  }

  function renderManager() {
    const entries = managerEntries();
    managerList.replaceChildren();
    const allMode = listScope === 'all';
    document.getElementById('list-manager-title').textContent = allMode ? 'Редактировать списки' : `Списки: ${currentGoal}`;
    document.getElementById('list-manager-description').textContent = allMode
      ? 'Переименуйте, удалите или добавьте список в нужный раздел.'
      : `${entries.length} из 5 · Переименуйте или удалите ненужный список.`;
    let previousGoal = '';
    entries.forEach(({item, goal, isOwner}, index) => {
      if (allMode && goal !== previousGoal) {
        const count = entries.filter((entry) => entry.goal === goal).length;
        appendManagerHeading(goal, count);
        previousGoal = goal;
      }
      const row = document.createElement('div');
      row.className = 'manager-row';
      row.dataset.kind = isOwner ? 'own' : 'joined';
      const number = document.createElement('span');
      number.className = 'manager-number';
      number.textContent = index + 1;
      const copy = document.createElement('span');
      copy.className = 'manager-copy';
      const title = document.createElement('strong');
      title.textContent = item.title;
      const note = document.createElement('small');
      note.textContent = isOwner ? listNote(item) : `${listNote(item)} · Доступ по приглашению`;
      copy.append(title, note);
      const actions = document.createElement('span');
      actions.className = 'manager-row-actions';
      if (isOwner) {
        const edit = makeManagerButton(`Редактировать: ${item.title}`, 'edit', '', () => openListEditor(item, goal));
        actions.append(edit);
      }
      if (isOwner || goal === 'Совместно') {
        const label = goal === 'Совместно' ? `Убрать у себя: ${item.title}` : `Удалить: ${item.title}`;
        const remove = makeManagerButton(label, 'trash', 'delete', () => requestListRemoval(item, goal));
        actions.append(remove);
      }
      row.append(number, copy, actions);
      managerList.append(row);
    });
    managerAddButton.classList.toggle('hidden', allMode);
    managerAddGoals.classList.toggle('hidden', !allMode);
    managerAddButton.disabled = !allMode && entries.length >= 5;
    managerAddGoals.querySelectorAll('[data-manager-add-goal]').forEach((button) => {
      button.disabled = serverApi.listsForGoal(button.dataset.managerAddGoal).length >= 5;
    });
  }

  function setManagerNavigation(label, icon) {
    document.getElementById('nav-manage-label').textContent = label;
    document.getElementById('nav-manage-symbol').setAttribute('href', `#${icon}`);
  }

  function openLists(goal) {
    onCloseShoppingList();
    listScope = 'goal';
    setActiveGoal(goal);
    listsKicker.textContent = 'Выберите список';
    listsTitle.textContent = goal;
    openManagerButton.classList.remove('hidden');
    setManagerNavigation('Добавить', 'plus');
    renderListOptions();
    homeView.classList.add('hidden');
    shoppingView.classList.add('hidden');
    listsView.classList.remove('hidden');
    app.classList.add('selection-mode');
    app.classList.remove('shopping-mode');
    app.classList.add('list-goal-mode');
    app.classList.remove('list-all-mode');
    setNavigation('lists');
    window.scrollTo({top: 0, behavior: 'auto'});
  }

  async function openListById(listId) {
    const found = serverApi.findList(listId);
    if (!found) return false;
    const goal = goalByKind[found.space.kind];
    await openShoppingList(found.list, goal);
    return true;
  }

  async function openAllLists() {
    onCloseShoppingList();
    try {
      await serverApi.refreshAccount();
    } catch (error) {
      showMessage(error.message);
      return;
    }
    listScope = 'all';
    listsKicker.textContent = 'Ваши покупки';
    listsTitle.textContent = 'Все списки';
    openManagerButton.classList.remove('hidden');
    setManagerNavigation('Править', 'edit');
    renderListOptions();
    homeView.classList.add('hidden');
    shoppingView.classList.add('hidden');
    listsView.classList.remove('hidden');
    app.classList.add('selection-mode');
    app.classList.remove('shopping-mode');
    app.classList.add('list-all-mode');
    app.classList.remove('list-goal-mode');
    setNavigation('lists');
    window.scrollTo({top: 0, behavior: 'auto'});
  }

  function closeLists() {
    onCloseShoppingList();
    listsView.classList.add('hidden');
    shoppingView.classList.add('hidden');
    homeView.classList.remove('hidden');
    app.classList.remove('selection-mode');
    app.classList.remove('shopping-mode');
    app.classList.remove('list-goal-mode', 'list-all-mode');
    setNavigation('home');
    window.scrollTo({top: 0, behavior: 'auto'});
  }

  document.querySelectorAll('[data-goal]').forEach((button) => {
    button.addEventListener('click', () => openLists(button.dataset.goal));
  });
  setActiveGoal(currentGoal);
  document.getElementById('nav-back').addEventListener('click', () => {
    if (!shoppingView.classList.contains('hidden')) {
      if (listScope === 'all') openAllLists();
      else openLists(currentGoal);
      return;
    }
    closeLists();
  });
  openManagerButton.addEventListener('click', openManager);
  document.getElementById('close-list-manager').addEventListener('click', () => managerModal.classList.add('hidden'));
  managerAddButton.addEventListener('click', () => openListEditor(null, currentGoal));
  managerAddGoals.querySelectorAll('[data-manager-add-goal]').forEach((button) => {
    button.addEventListener('click', () => openListEditor(null, button.dataset.managerAddGoal));
  });
  document.getElementById('cancel-custom-list').addEventListener('click', () => customModal.classList.add('hidden'));
  document.getElementById('close-list-removal').addEventListener('click', () => removalModal.classList.add('hidden'));
  document.getElementById('cancel-list-removal').addEventListener('click', () => removalModal.classList.add('hidden'));
  confirmRemovalButton.addEventListener('click', async () => {
    if (!pendingListRemoval) return;
    confirmRemovalButton.disabled = true;
    try {
      const {item, goal} = pendingListRemoval;
      removalModal.classList.add('hidden');
      await deleteList(item, goal);
      pendingListRemoval = null;
    } finally {
      confirmRemovalButton.disabled = false;
    }
  });
  saveCustomButton.addEventListener('click', async () => {
    const name = customName.value.trim();
    if (!name) return customName.focus();
    const duplicate = serverApi.listsForGoal(editingGoal)
      .some((item) => item.id !== editingListId && item.title.toLocaleLowerCase('ru') === name.toLocaleLowerCase('ru'));
    if (duplicate) {
      customModalDescription.textContent = 'Список с таким названием уже существует.';
      customName.focus();
      customName.select();
      return;
    }
    saveCustomButton.disabled = true;
    try {
      if (editingListId) await serverApi.updateList(editingListId, name);
      else await serverApi.createList(editingGoal, name);
      customModal.classList.add('hidden');
      managerModal.classList.add('hidden');
      renderListOptions();
      showMessage(editingListId ? `Список переименован: ${name}` : `Список добавлен: ${name}`);
    } catch (error) {
      customModalDescription.textContent = error.message;
    } finally {
      saveCustomButton.disabled = false;
    }
  });
  customName.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      saveCustomButton.click();
    }
  });

  return {
    openLists,
    openAllLists,
    closeLists,
    openListById,
    get currentGoal() { return currentGoal; },
    get selectedList() { return selectedList?.title || ''; },
    get selectedListId() { return selectedList?.id || ''; }
  };
}
