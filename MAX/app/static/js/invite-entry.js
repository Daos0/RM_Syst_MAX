const defaultDescription = 'Вставьте ссылку или код, который прислал организатор покупки.';

function extractInviteCode(value) {
  const source = value.trim();
  if (!source) return '';
  let candidate = source;
  try {
    const url = new URL(source);
    candidate = url.searchParams.get('start')
      || url.searchParams.get('startapp')
      || url.searchParams.get('WebAppStartParam')
      || url.searchParams.get('code')
      || '';
  } catch {
    candidate = source;
  }
  return candidate.replace(/^join[_-]/i, '').trim();
}

export function createInviteEntry({serverApi, listManager, showMessage}) {
  const modal = document.getElementById('invite-modal');
  const input = document.getElementById('invite-value');
  const description = document.getElementById('invite-description');

  function close() {
    modal.classList.add('hidden');
  }

  function open() {
    description.textContent = defaultDescription;
    modal.classList.remove('hidden');
    input.focus();
  }

  async function submit() {
    const code = extractInviteCode(input.value);
    if (!/^[A-Za-z0-9]{8}$/.test(code)) {
      description.textContent = 'Проверьте ссылку или код приглашения.';
      input.focus();
      input.select();
      return;
    }
    const submitButton = document.getElementById('submit-invite');
    submitButton.disabled = true;
    try {
      const result = await serverApi.acceptInvitation(code);
      close();
      input.value = '';
      if (result.kind === 'family') listManager.openLists('Для семьи');
      else await listManager.openListById(result.list_id);
      showMessage(result.joined
        ? `${result.kind === 'family' ? 'Вы вступили в семью' : 'Вы присоединились'}: ${result.title}`
        : `${result.kind === 'family' ? 'Семья' : 'Список'} уже доступна: ${result.title}`);
    } catch (error) {
      description.textContent = error.message;
      input.focus();
      input.select();
    } finally {
      submitButton.disabled = false;
    }
  }

  document.getElementById('open-invite').addEventListener('click', open);
  document.getElementById('close-invite').addEventListener('click', close);
  document.getElementById('submit-invite').addEventListener('click', submit);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') submit();
  });
}
