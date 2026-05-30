/** Группы каталога из API: сначала `groups`, иначе плоское слияние устаревших `sections`. */
export function catalogGroups(catalog) {
  if (!catalog) return [];
  if (Array.isArray(catalog.groups) && catalog.groups.length) return catalog.groups;
  return (catalog.sections || []).flatMap((sec) => sec.groups || []);
}

export function findCatalogGroup(catalog, groupId) {
  return catalogGroups(catalog).find((g) => g.id === groupId) ?? null;
}
