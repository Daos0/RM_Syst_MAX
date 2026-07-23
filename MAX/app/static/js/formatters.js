export function formatProductCount(value) {
  const count = Number(value) || 0;
  const lastTwo = count % 100;
  const last = count % 10;
  let word = 'товаров';
  if (lastTwo < 11 || lastTwo > 14) {
    if (last === 1) word = 'товар';
    else if (last >= 2 && last <= 4) word = 'товара';
  }
  return `${count} ${word}`;
}
