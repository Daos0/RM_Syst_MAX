export async function loadDatabaseCatalog() {
  const cacheKey = 'max.globalCatalog.v1';
  const maxAge = 5 * 60 * 1000;
  let cached = null;
  try {
    cached = JSON.parse(localStorage.getItem(cacheKey) || 'null');
    if (cached?.savedAt && Date.now() - cached.savedAt < maxAge) return cached.payload;
  } catch {
    localStorage.removeItem(cacheKey);
  }
  try {
    const response = await fetch('/api/v1/catalog', {headers: {'Accept': 'application/json'}});
    if (!response.ok) throw new Error(`Каталог недоступен: ${response.status}`);
    const payload = await response.json();
    if (!Array.isArray(payload.categories) || !Array.isArray(payload.products) || !Array.isArray(payload.recipes)) {
      throw new Error('Сервер вернул каталог неверного формата');
    }
    localStorage.setItem(cacheKey, JSON.stringify({savedAt: Date.now(), payload}));
    return payload;
  } catch (error) {
    if (cached?.payload) return cached.payload;
    throw error;
  }
}
