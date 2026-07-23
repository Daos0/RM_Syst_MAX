function positiveUsageItems(usage) {
  return Object.values(usage || {}).filter((item) => item && typeof item.name === 'string' && Number(item.count) > 0);
}

export function recommendedProductNames(productUsage, fallback, limit = 10) {
  const frequentItems = positiveUsageItems(productUsage)
    .sort((first, second) => Number(second.count) - Number(first.count) || first.name.localeCompare(second.name, 'ru'))
    .slice(0, limit);
  const frequent = frequentItems.map((item) => item.name);
  const names = [
    ...frequent,
    ...fallback.filter((name) => !frequent.some((item) => item.toLocaleLowerCase('ru') === name.toLocaleLowerCase('ru')))
  ].slice(0, limit);
  return {names, hasHistory: frequentItems.length > 0};
}

export function recipeRecommendationScore(recipe, productUsage, recipeUsage) {
  const ingredientNames = new Set(recipe.variants.flatMap((variant) => variant.ingredients.map(([name]) => name.toLocaleLowerCase('ru'))));
  const ingredientAffinity = [...ingredientNames].reduce((score, name) => {
    const purchases = Number(productUsage?.[name]?.count) || 0;
    return score + Math.log2(1 + purchases);
  }, 0);
  const recipeAffinity = (Number(recipeUsage?.[recipe.id]?.count) || 0) * 3;
  return recipeAffinity + ingredientAffinity / Math.sqrt(Math.max(ingredientNames.size, 1));
}

export function recommendedRecipes(recipes, productUsage, recipeUsage, query = '') {
  const normalized = query.trim().toLocaleLowerCase('ru');
  return recipes
    .map((recipe, catalogIndex) => ({recipe, catalogIndex, score: recipeRecommendationScore(recipe, productUsage, recipeUsage)}))
    .filter(({recipe}) => recipe.name.toLocaleLowerCase('ru').includes(normalized))
    .sort((first, second) => second.score - first.score || first.catalogIndex - second.catalogIndex)
    .map(({recipe}) => recipe);
}

export function hasPersonalizationSignals(productUsage, recipeUsage) {
  return positiveUsageItems(productUsage).length > 0 || positiveUsageItems(recipeUsage).length > 0;
}
