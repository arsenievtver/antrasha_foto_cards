import { useEffect, useState } from "react";
import { fetchCategoryOrderInsight } from "../api.js";
import { eur } from "../utils/money.js";

/**
 * Кружок «!» на плашке категории + модалка с рекомендациями и фактом заказов.
 * Данные тянем при открытии (актуальные суммы по брендам сезона).
 */
export default function CategoryInsightControl({
  categoryId,
  seasonId,
  categoryName,
}) {
  const [open, setOpen] = useState(false);

  if (!categoryId) return null;

  return (
    <>
      <button
        type="button"
        className="line-card__insight"
        aria-label={`Рекомендации: ${categoryName || "категория"}`}
        title="Рекомендации и заказы по категории"
        onClick={() => setOpen(true)}
      >
        !
      </button>
      {open ? (
        <CategoryInsightModal
          categoryId={categoryId}
          seasonId={seasonId}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}

function CategoryInsightModal({ categoryId, seasonId, onClose }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!seasonId) {
      setLoading(false);
      setErr("Сначала выберите сезон");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErr("");
    setData(null);
    fetchCategoryOrderInsight({ category_id: categoryId, season_id: seasonId })
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((e) => {
        if (!cancelled) setErr(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [categoryId, seasonId]);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const g = data?.guidance;
  const remaining = data?.remaining_eur;
  const remainingTone =
    remaining == null
      ? ""
      : Number(remaining) < 0
        ? " insight-modal__remain--over"
        : Number(remaining) === 0
          ? ""
          : " insight-modal__remain--ok";

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div
        className="modal-sheet insight-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="insight-modal__head">
          <h3>{data?.category_name || "Категория"}</h3>
          <button type="button" className="secondary insight-modal__close" onClick={onClose}>
            Закрыть
          </button>
        </div>

        {loading ? <p className="loading">Загрузка…</p> : null}
        {err ? <p className="error">{err}</p> : null}

        {!loading && !err && data ? (
          <div className="insight-modal__body">
            <section className="insight-modal__budget">
              <div>
                <span className="insight-modal__label">Бюджет</span>
                <strong>{data.budget_eur != null ? eur(data.budget_eur) : "—"}</strong>
              </div>
              <div>
                <span className="insight-modal__label">Уже заказано</span>
                <strong>{eur(data.ordered_eur)}</strong>
              </div>
              <div>
                <span className="insight-modal__label">Ещё можно</span>
                <strong className={remainingTone}>
                  {remaining != null ? eur(remaining) : "—"}
                </strong>
              </div>
            </section>

            {g ? (
              <section className="insight-modal__guidance">
                <p className="section-title" style={{ marginTop: 0 }}>
                  Рекомендации
                </p>
                {g.stock_totals ? (
                  <p className="guidance-card__stock">
                    Остатки: {g.stock_totals.total} шт (
                    {g.stock_totals.fresh_vl26 ?? 0};{g.stock_totals.old ?? 0}){" "}
                    {g.stock_totals.fresh_vl26 ?? 0}-ВЛ2026; {g.stock_totals.old ?? 0}
                    -старые
                  </p>
                ) : null}
                {g.reinforce_sizes?.length ? (
                  <p className="guidance-card__hint guidance-card__hint--up">
                    Усилить: {g.reinforce_sizes.join(", ")}
                  </p>
                ) : null}
                {g.weaken_sizes?.length ? (
                  <p className="guidance-card__hint guidance-card__hint--down">
                    Ослабить: {g.weaken_sizes.join(", ")}
                  </p>
                ) : (
                  <p className="guidance-card__hint">Ослабить: нет явных</p>
                )}
                {g.comment ? (
                  <p className="guidance-card__comment">{g.comment}</p>
                ) : null}
              </section>
            ) : (
              <p className="field-hint">Нет сохранённых рекомендаций по этой категории.</p>
            )}

            <section>
              <p className="section-title">Заказы по брендам</p>
              {data.brands?.length ? (
                <table className="guidance-table insight-modal__brands">
                  <thead>
                    <tr>
                      <th>Бренд</th>
                      <th>Заказано</th>
                      <th>Зак.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.brands.map((row) => (
                      <tr key={row.brand_id}>
                        <td>{row.brand_name}</td>
                        <td>{eur(row.amount_eur)}</td>
                        <td>{row.orders_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="field-hint">В этом сезоне по категории ещё нет заказов.</p>
              )}
            </section>
          </div>
        ) : null}
      </div>
    </div>
  );
}
