import { getVisibleExperienceCategories } from "../lib/experienceMenu";

const fixtureId = "6ad73dd525a6653d5f7c6a5a";

test("hides only the Chez Awa demo fixture and removes its empty category", () => {
  const categories = [
    { id: "fixture-category", name: "Fixture", items: [{ id: fixtureId, available: false }] },
    {
      id: "real-category",
      name: "Produits réels",
      items: [
        { id: "real-available", name: "Poulet braisé", available: true },
        { id: "real-unavailable", name: "Produit temporairement indisponible", available: false },
      ],
    },
    { id: "mixed-category", name: "Boissons", items: [{ id: fixtureId }, { id: "eau", name: "Eau", available: true }] },
  ];

  const visible = getVisibleExperienceCategories(categories);

  expect(visible.map((category) => category.id)).toEqual(["real-category", "mixed-category"]);
  expect(visible.flatMap((category) => category.items.map((item) => item.id))).toEqual([
    "real-available",
    "real-unavailable",
    "eau",
  ]);
});
