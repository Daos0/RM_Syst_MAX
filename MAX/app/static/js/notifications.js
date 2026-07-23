export function createNotification() {
  const toast = document.getElementById('toast');
  let timer;
  return (text) => {
    toast.textContent = text;
    toast.classList.add('show');
    clearTimeout(timer);
    timer = setTimeout(() => toast.classList.remove('show'), 1800);
  };
}
