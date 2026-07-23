import {readJson, storageKeys} from './storage.js?v=20260721-account';
import {
  initData as messengerInitData,
  platform,
  platformLabel,
  startParam as messengerStartParam
} from './platform-bridge.js?v=20260721-bot-links';

const goalKinds = Object.freeze({
  'Для себя': 'personal',
  'Для семьи': 'family',
  'Совместно': 'shared'
});

let sessionToken = '';

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers: {
      'Accept': 'application/json',
      ...(sessionToken ? {'Authorization': `Bearer ${sessionToken}`} : {}),
      ...(options.body ? {'Content-Type': 'application/json'} : {}),
      ...(options.headers || {})
    }
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Ошибка сервера: ${response.status}`);
  return payload;
}

function platformInitData() {
  const bridgeData = messengerInitData();
  if (bridgeData) return bridgeData;
  if (['127.0.0.1', 'localhost'].includes(window.location.hostname)) {
    const query = new URLSearchParams(window.location.search);
    return query.get(platform === 'telegram' ? 'telegram_init_data' : 'max_init_data') || '';
  }
  return '';
}

function isLocalPreview() {
  return ['127.0.0.1', 'localhost'].includes(window.location.hostname);
}

function emptyMigrationPayload() {
  return {
    migration_id: 'local_storage_v1',
    lists: [],
    personal_catalog: [],
    product_usage: {},
    recipe_usage: {}
  };
}

function legacyMigrationPayload() {
  const listSets = readJson(storageKeys.listSets);
  const shoppingLists = readJson(storageKeys.shoppingLists);
  const personalCatalog = readJson(storageKeys.personalCatalog);
  const lists = [];
  Object.entries(listSets).forEach(([goal, entries]) => {
    const category = goalKinds[goal];
    if (!category || !Array.isArray(entries)) return;
    entries.forEach((entry) => {
      const items = shoppingLists[`${goal}::${entry.name}`];
      lists.push({
        title: entry.name,
        category,
        items: Array.isArray(items) ? items.map((item) => ({
          name: item.name,
          quantity: Number(item.quantity) || 1,
          unit: item.unit || 'шт.',
          category: item.category || 'Другое',
          note: item.note || null,
          status: ['active', 'purchased', 'unavailable'].includes(item.status) ? item.status : 'active',
          mark: ['blue', 'amber', 'violet', 'coral'].includes(item.mark) ? item.mark : ''
        })) : []
      });
    });
  });
  return {
    migration_id: 'local_storage_v1',
    lists,
    personal_catalog: Object.values(personalCatalog).map((item) => ({
      name: item.name,
      quantity: Number(item.quantity) || 1,
      unit: item.unit || 'шт.',
      category: item.category || 'Другое'
    })),
    product_usage: readJson(storageKeys.productUsage),
    recipe_usage: readJson(storageKeys.recipeUsage)
  };
}

function clearLegacyData() {
  [
    storageKeys.listSets,
    storageKeys.legacyCustomLists,
    storageKeys.shoppingLists,
    storageKeys.personalCatalog,
    storageKeys.productUsage,
    storageKeys.recipeUsage
  ].forEach((key) => localStorage.removeItem(key));
}

function flattenList(payload) {
  return payload.departments.flatMap((department) => department.items.map((item) => ({
    id: item.id,
    productId: item.product_id,
    name: item.display_name,
    quantity: Number(item.quantity),
    unit: item.unit,
    step: ['кг', 'л'].includes(item.unit) ? 0.1 : 1,
    category: department.name,
    departmentId: item.department_id,
    note: item.note || '',
    mark: item.mark || '',
    status: item.status === 'assigned' ? 'active' : item.status,
    version: item.version
  })));
}

export async function initializeServerApi() {
  const startParam = messengerStartParam();
  let account = null;
  const forcedLocalInitData = isLocalPreview()
    ? new URLSearchParams(window.location.search).get(
      platform === 'telegram' ? 'telegram_init_data' : 'max_init_data'
    ) || ''
    : '';
  if (forcedLocalInitData) {
    account = await request(`/api/v1/auth/${platform}`, {
      method: 'POST',
      body: JSON.stringify({init_data: forcedLocalInitData})
    });
    sessionToken = account.session_token || '';
    delete account.session_token;
  } else {
    try {
      account = await request('/api/v1/auth/session');
    } catch (error) {
      const initData = platformInitData();
      if (!initData) throw new Error(`Откройте приложение из бота ${platformLabel}, чтобы подтвердить вход.`);
      account = await request(`/api/v1/auth/${platform}`, {
        method: 'POST',
        body: JSON.stringify({init_data: initData})
      });
      sessionToken = account.session_token || '';
      delete account.session_token;
    }
  }
  const localPreview = isLocalPreview();
  account = await request('/api/v1/migrations/local-storage', {
    method: 'POST',
    body: JSON.stringify(localPreview ? emptyMigrationPayload() : legacyMigrationPayload())
  });
  if (!localPreview) clearLegacyData();
  const reference = await request('/api/v1/reference');
  const departmentByName = new Map(reference.departments.map((item) => [item.name, item.id]));

  function spaceForGoal(goal) {
    const kind = goalKinds[goal];
    if (kind !== 'shared') return account.spaces.find((space) => space.kind === kind);
    return account.spaces.find((space) => space.kind === kind && space.title === 'Совместно' && space.is_owner)
      || account.spaces.find((space) => space.kind === kind && space.is_owner);
  }

  function listsForGoal(goal) {
    const kind = goalKinds[goal];
    return account.spaces
      .filter((space) => space.kind === kind)
      .flatMap((space) => space.lists);
  }

  function findList(listId) {
    for (const space of account.spaces) {
      const list = space.lists.find((item) => item.id === listId);
      if (list) return {space, list};
    }
    return null;
  }

  async function refreshAccount() {
    account = await request('/api/v1/auth/session');
    return account;
  }

  async function createList(goal, title, templateCode = null) {
    const space = spaceForGoal(goal);
    const created = await request(`/api/v1/spaces/${space.id}/lists`, {
      method: 'POST',
      body: JSON.stringify({title, category: space.kind, template_code: templateCode})
    });
    const list = {...created, item_count: 0, status: 'active', version: 1};
    if (created.space_id !== space.id) {
      account.spaces.push({
        id: created.space_id,
        title: created.space_title,
        kind: created.category,
        member_id: created.member_id,
        role: created.role,
        is_owner: true,
        lists: [list]
      });
    } else {
      space.lists.unshift(list);
    }
    return list;
  }

  async function updateList(listId, title) {
    const updated = await request(`/api/v1/lists/${listId}`, {
      method: 'PATCH', body: JSON.stringify({title})
    });
    account.spaces.forEach((space) => {
      const item = space.lists.find((row) => row.id === listId);
      if (item) Object.assign(item, updated);
    });
    return updated;
  }

  async function deleteList(listId) {
    await request(`/api/v1/lists/${listId}`, {method: 'DELETE'});
    await refreshAccount();
  }

  async function setListPinned(listId, pinned) {
    const updated = await request(`/api/v1/lists/${listId}/pin`, {
      method: 'PUT', body: JSON.stringify({pinned})
    });
    const found = findList(listId);
    if (found) found.list.is_pinned = updated.is_pinned;
    return updated;
  }

  async function getList(listId) {
    return flattenList(await request(`/api/v1/lists/${listId}`));
  }

  async function addItem(listId, values) {
    return request(`/api/v1/lists/${listId}/items`, {
      method: 'POST',
      body: JSON.stringify({
        name: values.name,
        quantity: values.quantity,
        unit: values.unit,
        department_id: departmentByName.get(values.category) || 14,
        note: values.note || null
      })
    });
  }

  async function addRecipe(listId, recipe, yieldQuantity, variantId, excludedProductIds) {
    return request(`/api/v1/lists/${listId}/recipes/${recipe.id}`, {
      method: 'POST',
      body: JSON.stringify({
        variant_id: variantId,
        yield_quantity: yieldQuantity,
        excluded_product_ids: excludedProductIds
      })
    });
  }

  async function updateItem(itemId, changes) {
    const payload = {...changes};
    if (payload.category) {
      payload.department_id = departmentByName.get(payload.category) || 14;
      delete payload.category;
    }
    delete payload.name;
    delete payload.step;
    delete payload.productId;
    return request(`/api/v1/items/${itemId}`, {method: 'PATCH', body: JSON.stringify(payload)});
  }

  async function deleteItem(itemId) {
    return request(`/api/v1/items/${itemId}`, {method: 'DELETE'});
  }

  async function setAllItemsStatus(listId, status) {
    return request(`/api/v1/lists/${listId}/items/status`, {
      method: 'PATCH',
      body: JSON.stringify({status})
    });
  }

  async function createInvitation(listId) {
    return request(`/api/v1/lists/${listId}/invitations`, {method: 'POST'});
  }

  async function acceptInvitation(code) {
    const result = await request(`/api/v1/invitations/${encodeURIComponent(code)}/accept`, {method: 'POST'});
    await refreshAccount();
    return result;
  }

  async function createFamilyInvitation(spaceId) {
    return request(`/api/v1/families/${spaceId}/invitations`, {method: 'POST'});
  }

  async function removeFamilyMember(spaceId, memberId) {
    await request(`/api/v1/families/${spaceId}/members/${memberId}`, {method: 'DELETE'});
    return refreshAccount();
  }

  async function leaveFamily(spaceId) {
    await request(`/api/v1/families/${spaceId}/leave`, {method: 'POST'});
    return refreshAccount();
  }

  return {
    get account() { return account; },
    get startParam() { return startParam; },
    get startListId() { return startParam.startsWith('open_') ? startParam.slice(5) : ''; },
    spaceForGoal,
    listsForGoal,
    findList,
    refreshAccount,
    createList,
    updateList,
    deleteList,
    setListPinned,
    getList,
    addItem,
    addRecipe,
    updateItem,
    deleteItem,
    setAllItemsStatus,
    createInvitation,
    acceptInvitation,
    createFamilyInvitation,
    removeFamilyMember,
    leaveFamily
  };
}
