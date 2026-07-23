import {
  invitationBotUrl,
  invitationShareUrl,
  openMessengerLink,
  platformLabel
} from './platform-bridge.js?v=20260721-bot-links';

export function createListSharing({serverApi, getListId, showMessage}) {
  const modal = document.getElementById('share-list-modal');
  const description = document.getElementById('share-list-description');
  const codeBlock = document.getElementById('share-code-block');
  const codeValue = document.getElementById('share-list-code');
  const sendButton = document.getElementById('send-share-list');
  const copyButton = document.getElementById('copy-share-list');
  let invitation = null;

  function showCopied() {
    const original = copyButton.innerHTML;
    copyButton.classList.add('copied');
    copyButton.textContent = '✓ Ссылка скопирована';
    copyButton.disabled = true;
    window.setTimeout(() => {
      copyButton.innerHTML = original;
      copyButton.classList.remove('copied');
      copyButton.disabled = false;
    }, 1800);
  }

  function close() {
    modal.classList.add('hidden');
  }

  async function copyLink() {
    if (!invitation) return;
    try {
      await navigator.clipboard.writeText(invitationBotUrl(invitation));
      showCopied();
      showMessage('Ссылка скопирована');
    } catch {
      showMessage(`Код приглашения: ${invitation.code}`);
    }
  }

  function sendInvitation() {
    if (!invitation) return;
    if (!openMessengerLink(invitationShareUrl(invitation))) copyLink();
  }

  async function open(requestedListId = '') {
    const listId = requestedListId || getListId();
    if (!listId) return;
    invitation = null;
    description.textContent = 'Создаём безопасное приглашение…';
    codeBlock.classList.add('hidden');
    sendButton.disabled = true;
    copyButton.disabled = true;
    modal.classList.remove('hidden');
    try {
      invitation = await serverApi.createInvitation(listId);
      codeValue.textContent = invitation.code;
      description.textContent = `Ссылка откроет бота ${platformLabel}. После запуска список сразу появится у участника.`;
      codeBlock.classList.remove('hidden');
      sendButton.disabled = false;
      copyButton.disabled = false;
    } catch (error) {
      description.textContent = error.message;
    }
  }

  document.getElementById('shopping-share').addEventListener('click', () => open());
  document.getElementById('close-share-list').addEventListener('click', close);
  sendButton.addEventListener('click', sendInvitation);
  copyButton.addEventListener('click', copyLink);

  return {open, close};
}
