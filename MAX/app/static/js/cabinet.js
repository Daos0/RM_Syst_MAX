import {
  invitationBotUrl,
  invitationShareUrl,
  openMessengerLink,
  platformLabel
} from './platform-bridge.js?v=20260721-bot-links';

export function createCabinet({serverApi, listManager, showMessage}) {
  const app = document.querySelector('.app');
  const cabinetView = document.getElementById('cabinet-view');
  const homeView = document.getElementById('home-view');
  const listsView = document.getElementById('lists-view');
  const shoppingView = document.getElementById('shopping-view');
  const familyCard = document.getElementById('family-card');
  const inviteModal = document.getElementById('family-invite-modal');
  const inviteDescription = document.getElementById('family-invite-description');
  const inviteCodeBlock = document.getElementById('family-code-block');
  const inviteCode = document.getElementById('family-invite-code');
  const sendInviteButton = document.getElementById('send-family-invite');
  const copyInviteButton = document.getElementById('copy-family-invite');
  const actionModal = document.getElementById('family-action-modal');
  const actionTitle = document.getElementById('family-action-title');
  const actionDescription = document.getElementById('family-action-description');
  const confirmActionButton = document.getElementById('confirm-family-action');
  const guideToggle = document.getElementById('cabinet-guide-toggle');
  const guideContent = document.getElementById('cabinet-guide-content');
  let familyInvitation = null;
  let pendingAction = null;

  function setGuideOpen(opened) {
    guideToggle.setAttribute('aria-expanded', String(opened));
    guideContent.classList.toggle('hidden', !opened);
  }

  function formatMemberCount(count) {
    const lastTwo = count % 100;
    const last = count % 10;
    if (lastTwo >= 11 && lastTwo <= 14) return `${count} участников`;
    if (last === 1) return `${count} участник`;
    if (last >= 2 && last <= 4) return `${count} участника`;
    return `${count} участников`;
  }

  function setNavigation(active) {
    document.querySelectorAll('[data-nav]').forEach((button) => {
      const isActive = button.dataset.nav === active;
      button.classList.toggle('active', isActive);
      if (isActive) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
  }

  function avatarFor(member) {
    const avatar = document.createElement('span');
    avatar.className = 'family-member-avatar';
    if (member.avatar_url) {
      const image = document.createElement('img');
      image.src = member.avatar_url;
      image.alt = '';
      avatar.append(image);
    } else {
      avatar.textContent = member.display_name.trim().charAt(0).toLocaleUpperCase('ru');
    }
    return avatar;
  }

  function openFamilyAction({title, description, button, action}) {
    actionTitle.textContent = title;
    actionDescription.textContent = description;
    confirmActionButton.textContent = button;
    pendingAction = action;
    actionModal.classList.remove('hidden');
  }

  function memberRow(member, familySpace) {
    const row = document.createElement('div');
    row.className = 'family-member';
    const copy = document.createElement('span');
    copy.className = 'family-member-copy';
    const name = document.createElement('strong');
    name.textContent = member.display_name;
    const note = document.createElement('small');
    const role = member.role === 'owner' ? 'Владелец семьи' : 'Участник семьи';
    note.textContent = member.is_current ? `Это вы · ${role}` : (member.username ? `@${member.username} · ${role}` : role);
    copy.append(name, note);
    row.append(avatarFor(member), copy);
    if (familySpace.is_owner && !member.is_current) {
      const remove = document.createElement('button');
      remove.className = 'family-member-remove';
      remove.type = 'button';
      remove.setAttribute('aria-label', `Исключить: ${member.display_name}`);
      remove.innerHTML = '<svg aria-hidden="true"><use href="#trash"/></svg>';
      remove.addEventListener('click', () => openFamilyAction({
        title: `Исключить ${member.display_name}?`,
        description: 'Участник потеряет доступ к семейным спискам. Его личные списки останутся у него.',
        button: 'Исключить',
        async action() {
          await serverApi.removeFamilyMember(familySpace.id, member.id);
          render();
          showMessage(`${member.display_name} исключён из семьи`);
        }
      }));
      row.append(remove);
    }
    return row;
  }

  async function openFamilyInvite(familySpace) {
    familyInvitation = null;
    inviteDescription.textContent = 'Создаём безопасное приглашение…';
    inviteCodeBlock.classList.add('hidden');
    sendInviteButton.disabled = true;
    copyInviteButton.disabled = true;
    inviteModal.classList.remove('hidden');
    try {
      familyInvitation = await serverApi.createFamilyInvitation(familySpace.id);
      inviteCode.textContent = familyInvitation.code;
      inviteDescription.textContent = `Ссылка откроет бота ${platformLabel}. После запуска участник появится в вашей семье.`;
      inviteCodeBlock.classList.remove('hidden');
      sendInviteButton.disabled = false;
      copyInviteButton.disabled = false;
    } catch (error) {
      inviteDescription.textContent = error.message;
    }
  }

  async function copyFamilyInvite() {
    if (!familyInvitation) return;
    try {
      await navigator.clipboard.writeText(invitationBotUrl(familyInvitation));
      const original = copyInviteButton.innerHTML;
      copyInviteButton.classList.add('copied');
      copyInviteButton.textContent = '✓ Ссылка скопирована';
      copyInviteButton.disabled = true;
      window.setTimeout(() => {
        copyInviteButton.innerHTML = original;
        copyInviteButton.classList.remove('copied');
        copyInviteButton.disabled = false;
      }, 1800);
      showMessage('Ссылка на семью скопирована');
    } catch {
      showMessage(`Код приглашения: ${familyInvitation.code}`);
    }
  }

  function renderFamily(spaces) {
    const familySpace = spaces.find((space) => space.kind === 'family');
    familyCard.replaceChildren();
    if (!familySpace) return;
    const members = familySpace.members || [];
    document.getElementById('family-section-note').textContent = familySpace.is_owner
      ? 'Вы управляете группой'
      : 'Общие покупки семьи';
    const summary = document.createElement('div');
    summary.className = 'family-summary';
    summary.innerHTML = '<span class="family-summary-icon"><svg aria-hidden="true"><use href="#users"/></svg></span>';
    const copy = document.createElement('span');
    copy.className = 'family-summary-copy';
    const title = document.createElement('strong');
    title.textContent = members.length > 1 ? 'Ваша семья' : 'Семья начинается здесь';
    const note = document.createElement('small');
    note.textContent = members.length === 1 ? 'Пока только вы' : formatMemberCount(members.length);
    copy.append(title, note);
    const role = document.createElement('span');
    role.className = 'family-role';
    role.textContent = familySpace.is_owner ? 'Владелец' : 'Участник';
    summary.append(copy, role);
    const memberList = document.createElement('div');
    memberList.className = 'family-members';
    members.forEach((member) => memberList.append(memberRow(member, familySpace)));
    const actions = document.createElement('div');
    actions.className = 'family-actions';
    const action = document.createElement('button');
    action.type = 'button';
    if (familySpace.is_owner) {
      action.className = 'family-primary';
      action.innerHTML = '<svg aria-hidden="true"><use href="#plus"/></svg>Пригласить участника';
      action.addEventListener('click', () => openFamilyInvite(familySpace));
    } else {
      action.className = 'family-leave';
      action.innerHTML = '<svg aria-hidden="true"><use href="#sliders"/></svg>Настройки участия';
      action.addEventListener('click', () => openFamilyAction({
        title: 'Выйти из семейной группы?',
        description: 'Вы потеряете доступ к семейным спискам. Ваши личные списки останутся на месте.',
        button: 'Выйти',
        async action() {
          await serverApi.leaveFamily(familySpace.id);
          render();
          showMessage('Вы вышли из семейной группы');
        }
      }));
    }
    actions.append(action);
    familyCard.append(summary, memberList, actions);
  }

  function render() {
    const {user, spaces} = serverApi.account;
    const avatar = document.getElementById('profile-avatar');
    avatar.replaceChildren();
    if (user.avatar_url) {
      const image = document.createElement('img');
      image.src = user.avatar_url;
      image.alt = '';
      avatar.append(image);
    } else {
      avatar.textContent = user.display_name.trim().charAt(0).toLocaleUpperCase('ru');
    }
    document.getElementById('profile-name').textContent = user.display_name;
    document.getElementById('profile-username').textContent = user.username
      ? `@${user.username}`
      : 'Профиль покупателя';
    renderFamily(spaces);
  }

  async function open() {
    try {
      await serverApi.refreshAccount();
      render();
      homeView.classList.add('hidden');
      listsView.classList.add('hidden');
      shoppingView.classList.add('hidden');
      cabinetView.classList.remove('hidden');
      app.classList.remove('selection-mode', 'shopping-mode', 'list-goal-mode', 'list-all-mode');
      setNavigation('cabinet');
      window.scrollTo({top: 0, behavior: 'auto'});
    } catch (error) {
      showMessage(error.message);
    }
  }

  function close() {
    cabinetView.classList.add('hidden');
    listManager.closeLists();
    setNavigation('home');
  }

  document.querySelector('[data-nav="home"]').addEventListener('click', close);
  document.querySelector('[data-nav="lists"]').addEventListener('click', () => {
    cabinetView.classList.add('hidden');
    listManager.openAllLists();
    setNavigation('lists');
  });
  document.querySelector('[data-nav="cabinet"]').addEventListener('click', open);
  document.getElementById('close-family-invite').addEventListener('click', () => inviteModal.classList.add('hidden'));
  copyInviteButton.addEventListener('click', copyFamilyInvite);
  sendInviteButton.addEventListener('click', () => {
    if (!familyInvitation) return;
    if (!openMessengerLink(invitationShareUrl(familyInvitation))) copyFamilyInvite();
  });
  document.getElementById('cancel-family-action').addEventListener('click', () => actionModal.classList.add('hidden'));
  guideToggle.addEventListener('click', () => {
    setGuideOpen(guideToggle.getAttribute('aria-expanded') !== 'true');
  });
  document.getElementById('close-cabinet-guide').addEventListener('click', () => setGuideOpen(false));
  confirmActionButton.addEventListener('click', async () => {
    if (!pendingAction) return;
    confirmActionButton.disabled = true;
    try {
      await pendingAction();
      actionModal.classList.add('hidden');
    } catch (error) {
      actionDescription.textContent = error.message;
    } finally {
      confirmActionButton.disabled = false;
    }
  });
  return {open, close};
}
