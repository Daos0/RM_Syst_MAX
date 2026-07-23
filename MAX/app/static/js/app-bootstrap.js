import {hydrateProductCatalog} from './catalog.js?v=20260720-database-catalog';
import {loadDatabaseCatalog} from './catalog-api.js?v=20260720-database-catalog';
import {hydrateGroceryCatalog} from './grocery.js?v=20260720-database-catalog';
import {hydrateRecipeCatalog} from './recipes.js?v=20260720-database-catalog';
import {hydrateSupplyCatalog} from './supplies.js?v=20260720-database-catalog';
import {initializeServerApi} from './server-api.js?v=20260721-realtime';
import {ready} from './platform-bridge.js?v=20260721-bot-links';

function trackVisibleViewport() {
  const viewport = window.visualViewport;
  const update = () => {
    const height = Math.round(viewport?.height || window.innerHeight);
    const offsetTop = Math.round(viewport?.offsetTop || 0);
    document.documentElement.style.setProperty('--visible-viewport-height', `${height}px`);
    document.documentElement.style.setProperty('--visible-viewport-top', `${offsetTop}px`);
  };
  update();
  viewport?.addEventListener('resize', update);
  viewport?.addEventListener('scroll', update);
  window.addEventListener('resize', update);
}

export async function initializeApp() {
  trackVisibleViewport();
  try {
    const serverApi = await initializeServerApi();
    const catalog = await loadDatabaseCatalog();
    hydrateProductCatalog(catalog.products);
    hydrateGroceryCatalog(catalog.categories, catalog.products);
    hydrateRecipeCatalog(catalog.categories, catalog.recipes);
    hydrateSupplyCatalog(catalog.categories, catalog.products);
    document.querySelector('.app').classList.remove('booting');
    document.getElementById('auth-gate').classList.add('hidden');
    ready();
    return serverApi;
  } catch (error) {
    document.getElementById('auth-gate-message').textContent = error.message;
    ready();
    throw error;
  }
}
