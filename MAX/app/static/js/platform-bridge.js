function localPlatform() {
  if (!['127.0.0.1', 'localhost'].includes(window.location.hostname)) return '';
  return new URLSearchParams(window.location.search).get('platform') || '';
}

const telegramApp = window.Telegram?.WebApp;
const maxApp = window.WebApp;
const forcedPlatform = localPlatform();

export const platform = forcedPlatform === 'telegram' || (!maxApp?.initData && telegramApp?.initData)
  ? 'telegram'
  : 'max';
export const platformLabel = platform === 'telegram' ? 'Telegram' : 'MAX';

export function initData() {
  if (platform === 'telegram') return telegramApp?.initData || '';
  const bridgeData = maxApp?.initData || '';
  if (bridgeData) return bridgeData;
  return new URLSearchParams(window.location.hash.slice(1)).get('WebAppData') || '';
}

export function startParam() {
  const app = platform === 'telegram' ? telegramApp : maxApp;
  const unsafe = app?.initDataUnsafe?.start_param;
  if (typeof unsafe === 'string' && unsafe) return unsafe;
  const query = new URLSearchParams(window.location.search);
  return query.get(platform === 'telegram' ? 'tgWebAppStartParam' : 'WebAppStartParam')
    || query.get('startapp')
    || (initData() ? new URLSearchParams(initData()).get('start_param') || '' : '');
}

export function ready() {
  const app = platform === 'telegram' ? telegramApp : maxApp;
  app?.ready?.();
  app?.expand?.();
}

export function invitationShareUrl(invitation) {
  return invitation?.share_urls?.[platform] || invitation?.share_url || '';
}

export function invitationBotUrl(invitation) {
  return invitation?.bot_urls?.[platform] || invitation?.bot_url || '';
}

export function openMessengerLink(url) {
  if (!url) return false;
  if (platform === 'telegram' && telegramApp?.openTelegramLink) {
    telegramApp.openTelegramLink(url);
    return true;
  }
  if (platform === 'max' && maxApp?.openMaxLink) {
    maxApp.openMaxLink(url);
    return true;
  }
  window.open(url, '_blank', 'noopener,noreferrer');
  return true;
}
