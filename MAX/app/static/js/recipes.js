export const recipeGroups = [];
export const recipeCatalog = [];

export function hydrateRecipeCatalog(categories, recipes) {
  const groups = categories
    .filter((category) => category.kind === 'dish')
    .sort((first, second) => first.sort_order - second.sort_order)
    .map((category) => ({id: category.code, name: category.name, icon: category.icon}));
  const items = recipes
    .sort((first, second) => first.sort_order - second.sort_order)
    .map((recipe) => ({
      id: recipe.id,
      code: recipe.code,
      group: recipe.category_code,
      name: recipe.name,
      icon: recipe.icon,
      note: recipe.description,
      yield: {
        label: recipe.yield.label,
        quantity: Number(recipe.yield.quantity),
        unit: recipe.yield.unit,
        step: Number(recipe.yield.step)
      },
      variants: recipe.variants.map((variant) => ({
        id: variant.id,
        code: variant.code,
        name: variant.name,
        ingredients: variant.ingredients.map((ingredient) => [
          ingredient.name,
          Number(ingredient.quantity),
          ingredient.unit,
          ingredient.product_id
        ])
      }))
    }));
  recipeGroups.splice(0, recipeGroups.length, ...groups);
  recipeCatalog.splice(0, recipeCatalog.length, ...items);
}

export function scaledRecipeIngredients(recipeItem, variantId, targetYield) {
  const variant = recipeItem.variants.find((item) => item.id === variantId) || recipeItem.variants[0];
  const factor = Number(targetYield) / recipeItem.yield.quantity;
  return variant.ingredients.map(([name, quantity, unit, productId], index) => ({
    id: `${variant.id}-${index}`,
    productId,
    name,
    quantity: Math.round((quantity * factor + Number.EPSILON) * 100) / 100,
    unit
  }));
}
