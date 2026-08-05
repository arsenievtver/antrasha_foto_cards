const CATEGORY_RULES = {
  men: [
    {
      label: "Верхняя одежда муж",
      ids: ["0ebca617-f97a-11e9-0a80-0579004f6022"],
      names: ["Верхняя одежда муж"],
    },
    {
      label: "Пиджаки, жакеты, бомбер муж",
      ids: ["009bd151-b37b-11e9-9ff4-3150003a1bb1"],
      names: ["Пиджаки, жакеты, бомбер муж"],
    },
    {
      label: "Футболки, поло муж",
      ids: ["46a5c5b7-5708-11e9-9ff4-315000d0798d"],
      names: ["Футболки, поло муж"],
    },
    {
      label: "Брюки, джинсы муж",
      ids: ["46b4f0d3-5708-11e9-9ff4-315000d079ad"],
      names: [
        "Брюки, джинсы муж",
        "Брюки, джинсы, бриджи, шорты муж",
      ],
    },
    {
      label: "Бриджи, шорты муж",
      ids: ["55edd126-8bff-11f1-0a80-142f000aee50"],
      names: ["Бриджи, шорты муж"],
    },
    {
      label: "Трикотаж муж",
      ids: ["7958c78e-9e44-11e9-9ff4-31500007d713"],
      names: ["Трикотаж муж"],
    },
    {
      label: "Рубашки",
      ids: ["797d0e35-9e44-11e9-9ff4-31500007d733"],
      names: ["Рубашки"],
    },
    {
      label: "Костюмы муж",
      ids: ["eec41100-9847-11eb-0a80-0616000ac009"],
      names: ["Костюмы муж"],
    },
    {
      label: "Обувь муж",
      ids: ["f8fae156-b37a-11e9-9ff4-3150003a11ec"],
      names: ["Обувь муж"],
    },
  ],
  women: [
    {
      label: "Верхняя одежда жен",
      ids: ["0dea4445-f97a-11e9-0a80-0579004f5ecf"],
      names: ["Верхняя одежда жен"],
    },
    {
      label: "Пиджаки, жакеты, бомбер жен",
      ids: [
        "79292943-9e44-11e9-9ff4-31500007d6f3",
        "463e7bec-34dd-11f1-0a80-148d00118078",
      ],
      names: ["Пиджаки, жакеты, бомбер жен", "Пиджаки, жакеты, бомбер"],
    },
    {
      label: "Футболки, поло, топы жен",
      ids: ["f7b6946e-b37a-11e9-9ff4-3150003a0ff5"],
      names: ["Футболки, поло, топы жен"],
    },
    {
      label: "Блузки, рубашки жен",
      ids: ["21e1d207-b53f-11e9-9ff4-31500015315b"],
      names: ["Блузки, рубашки", "Блузки, рубашки жен"],
    },
    {
      label: "Трикотаж жен",
      ids: ["cd27a401-d3a6-11e9-0a80-02690003e199"],
      names: ["Трикотаж жен"],
    },
    {
      label: "Брюки, джинсы жен",
      ids: [
        "78fabba1-9e44-11e9-9ff4-31500007d6c1",
        "8ade28c6-6e3e-11f1-0a80-00b0001171b1",
      ],
      names: [
        "Брюки, джинсы жен",
        "Брюки, джинсы, бриджи, шорты жен",
        "Брюки, джинсы, бриджи, шорты",
      ],
    },
    {
      label: "Бриджи, шорты жен",
      ids: ["4643b20e-8bfa-11f1-0a80-18830009f9ac"],
      names: ["Бриджи, шорты жен"],
    },
    {
      label: "Платья жен",
      ids: ["65dca14b-8bfd-11f1-0a80-0fbf000a6721"],
      names: ["Платья жен", "Платья"],
    },
    {
      label: "Юбки жен",
      ids: ["26114fa1-a495-11e9-9ff4-3150000fa9a1"],
      names: [
        "Юбки жен",
        "Юбки",
        "Платья, юбки",
        "Платья, юбки жен",
      ],
    },
    {
      label: "Обувь жен",
      ids: ["79419e87-9e44-11e9-9ff4-31500007d6fe"],
      names: ["Обувь жен"],
    },
  ],
};

function findCanonical(defs, categoryId) {
  if (!categoryId) return null;
  return defs.find((def) => def.ids.includes(categoryId)) || null;
}

export function normalizeCategoryId(categoryId, gender) {
  if (!categoryId || !gender || !CATEGORY_RULES[gender]) return categoryId;
  const canonical = findCanonical(CATEGORY_RULES[gender], categoryId);
  return canonical ? canonical.ids[0] : categoryId;
}

export function getFormCategories(allCategories, gender) {
  const all = allCategories || [];
  if (!gender || gender === "mixed") return all;

  const defs = CATEGORY_RULES[gender];
  if (!defs) return all;

  const byId = new Map();
  for (const c of all) {
    byId.set(String(c.id), c);
    if (c.moy_sklad_id) byId.set(c.moy_sklad_id, c);
  }

  return defs
    .map((def) => {
      const byRuleId = def.ids.find((id) => byId.has(id));
      if (byRuleId) return { ...byId.get(byRuleId), name: def.label };

      const byRuleName = all.find(
        (c) => c.gender === gender && def.names.includes(c.name),
      );
      if (byRuleName) return { ...byRuleName, name: def.label };
      return null;
    })
    .filter(Boolean);
}
