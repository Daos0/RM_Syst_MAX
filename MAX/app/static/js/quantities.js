export function unitsCompatible(first, second) {
  if (first === second) return true;
  return [['кг', 'г'], ['л', 'мл']].some((group) => group.includes(first) && group.includes(second));
}

export function convertQuantity(quantity, from, to) {
  if (from === to) return quantity;
  if (from === 'кг' && to === 'г') return quantity * 1000;
  if (from === 'г' && to === 'кг') return quantity / 1000;
  if (from === 'л' && to === 'мл') return quantity * 1000;
  if (from === 'мл' && to === 'л') return quantity / 1000;
  return quantity;
}
