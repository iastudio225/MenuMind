const HIDDEN_DEMO_ITEM_IDS = new Set(["6ad73dd525a6653d5f7c6a5a"]);

export function getVisibleExperienceCategories(categories = []) {
  return categories
    .map((category) => ({
      ...category,
      items: (category.items || []).filter((item) => !HIDDEN_DEMO_ITEM_IDS.has(item.id)),
    }))
    .filter((category) => category.items.length > 0);
}
