import { useMemo } from "react";
import CategoryInsightControl from "./CategoryInsightControl.jsx";
import { num } from "../utils/money.js";
import {
  getGroupedFormCategories,
  lineChoiceCategoryId,
  lineChoiceFromOrderLine,
  lineChoiceToPayload,
} from "../utils/procurementCategories.js";

export function newOrderLine(line) {
  return {
    key: crypto.randomUUID(),
    choice: lineChoiceFromOrderLine(line),
    amount_eur: line?.amount_eur || "",
    comment: line?.comment || "",
  };
}

export function filledOrderLines(lines) {
  return lines.filter((ln) => ln.choice && num(ln.amount_eur) > 0);
}

export function orderLinesPayload(lines) {
  return filledOrderLines(lines).map((ln) => ({
    ...lineChoiceToPayload(ln.choice),
    amount_eur: ln.amount_eur,
    comment: ln.comment.trim() || null,
  }));
}

export default function OrderLinesEditor({ categories, seasonId, lines, setLines }) {
  const groups = useMemo(() => getGroupedFormCategories(categories), [categories]);
  const nameById = useMemo(() => {
    const map = new Map();
    for (const group of groups) {
      for (const c of group.items) map.set(String(c.id), c.name);
    }
    return map;
  }, [groups]);

  function setLine(key, field, value) {
    setLines((prev) => prev.map((ln) => (ln.key === key ? { ...ln, [field]: value } : ln)));
  }

  return (
    <>
      {lines.map((ln) => {
        const categoryId = lineChoiceCategoryId(ln.choice);
        return (
          <div key={ln.key} className="line-card">
            <CategoryInsightControl
              categoryId={categoryId}
              seasonId={seasonId}
              categoryName={nameById.get(categoryId)}
            />
            <label>
              Категория
              <select
                value={ln.choice}
                onChange={(e) => setLine(ln.key, "choice", e.target.value)}
              >
                <option value="">— выберите —</option>
                {groups.map((group) => (
                  <optgroup key={group.gender} label={group.label}>
                    {group.items.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                    <option value={`none:${group.gender}`}>{group.unsplitLabel}</option>
                  </optgroup>
                ))}
              </select>
            </label>
            <label>
              Сумма, €
              <input
                type="number"
                step="0.01"
                min="0"
                inputMode="decimal"
                value={ln.amount_eur}
                onChange={(e) => setLine(ln.key, "amount_eur", e.target.value)}
              />
            </label>
            <label>
              Комментарий
              <input
                value={ln.comment}
                onChange={(e) => setLine(ln.key, "comment", e.target.value)}
              />
            </label>
            <button
              type="button"
              className="secondary"
              onClick={() => setLines((prev) => prev.filter((x) => x.key !== ln.key))}
            >
              Убрать
            </button>
          </div>
        );
      })}
      <button
        type="button"
        className="secondary"
        onClick={() => setLines((prev) => [...prev, newOrderLine()])}
      >
        + Строка
      </button>
    </>
  );
}
