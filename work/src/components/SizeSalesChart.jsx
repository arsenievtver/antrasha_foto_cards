/** Бар-чарт продаж по размерам (как на экране «Для заказа»). */
export default function SizeSalesChart({ labels, values, reinforce, weaken }) {
  const max = Math.max(1, ...values.map((v) => Number(v) || 0));
  const reinforceSet = reinforce instanceof Set ? reinforce : new Set(reinforce || []);
  const weakenSet = weaken instanceof Set ? weaken : new Set(weaken || []);

  return (
    <div className="size-chart" aria-label="Продажи по размерам">
      <p className="size-chart__caption">Продано ВЛ2025+ВЛ2026 (шт)</p>
      <div className="size-chart__bars">
        {labels.map((label, i) => {
          const qty = Number(values[i]) || 0;
          const h = Math.round((qty / max) * 100);
          let tone = "";
          if (reinforceSet.has(label)) tone = " size-chart__col--up";
          else if (weakenSet.has(label)) tone = " size-chart__col--down";
          return (
            <div key={`${label}-${i}`} className={`size-chart__col${tone}`}>
              <span className="size-chart__qty">{qty || ""}</span>
              <div className="size-chart__bar-wrap">
                <div className="size-chart__bar" style={{ height: `${h}%` }} />
              </div>
              <span className="size-chart__label">{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
