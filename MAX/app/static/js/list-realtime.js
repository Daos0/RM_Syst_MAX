export function createListRealtime({onChanged, onAccessLost}) {
  let source = null;
  let currentListId = '';
  let refreshing = false;
  let refreshQueued = false;
  let fallbackTimer = null;
  let connectionTimer = null;

  function stopFallback() {
    clearInterval(fallbackTimer);
    fallbackTimer = null;
  }

  function startFallback() {
    if (fallbackTimer) return;
    fallbackTimer = setInterval(refresh, 1000);
  }

  function disconnect() {
    source?.close();
    source = null;
    clearTimeout(connectionTimer);
    connectionTimer = null;
    stopFallback();
  }

  async function refresh() {
    if (refreshing) {
      refreshQueued = true;
      return;
    }
    refreshing = true;
    try {
      do {
        refreshQueued = false;
        await onChanged(currentListId);
      } while (refreshQueued && currentListId);
    } finally {
      refreshing = false;
    }
  }

  function connect() {
    disconnect();
    if (!currentListId) return;
    try {
      source = new EventSource(`/api/v1/lists/${encodeURIComponent(currentListId)}/events`, {
        withCredentials: true
      });
      connectionTimer = setTimeout(startFallback, 1500);
      source.addEventListener('open', () => {
        clearTimeout(connectionTimer);
        connectionTimer = null;
        stopFallback();
      });
      source.addEventListener('error', startFallback);
      source.addEventListener('list_changed', refresh);
      source.addEventListener('access_revoked', async () => {
        const lostListId = currentListId;
        close();
        await onAccessLost(lostListId);
      });
    } catch {
      source = null;
      startFallback();
    }
  }

  function watch(listId) {
    if (!listId) return close();
    if (currentListId === listId && source) return;
    currentListId = listId;
    connect();
  }

  function close() {
    currentListId = '';
    disconnect();
  }

  document.addEventListener('visibilitychange', async () => {
    if (!currentListId || document.visibilityState === 'hidden') return;
    await refresh();
    if (!source && !fallbackTimer) connect();
  });

  return {watch, close};
}
