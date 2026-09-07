/** Блок логистики и статуса доставки — create/edit поставки (mobile-first). */
export default function ShipmentLogisticsSection({ form, setField }) {
  const delivered = !!form.is_delivered;

  return (
    <div className="form-section">
      <h3 className="form-section__title">Логистика</h3>
      <p className="form-section__hint">
        Отдельно от оплаты бренду. Можно заполнить заранее, пока груз ещё в пути.
      </p>

      <div className="form-row form-row--2col">
        <label>
          Сумма, ₽
          <input
            type="number"
            step="0.01"
            min="0"
            inputMode="decimal"
            value={form.logistics_amount_rub}
            onChange={(e) => setField("logistics_amount_rub", e.target.value)}
            placeholder="0"
          />
        </label>
        <label>
          Дата оплаты
          <input
            type="date"
            value={form.logistics_paid_on}
            onChange={(e) => setField("logistics_paid_on", e.target.value)}
          />
        </label>
      </div>

      <div className="form-switch-row">
        <div className="form-switch-row__text">
          <div className="form-switch-row__label">
            {delivered ? "Поставлено" : "В пути"}
          </div>
          <div className="form-switch-row__hint">
            {delivered
              ? "Учитывается в «осталось поставить» по заказу"
              : "Не уменьшает остаток — пока груз не получен"}
          </div>
        </div>
        <button
          type="button"
          className="switch-toggle"
          role="switch"
          aria-checked={delivered}
          aria-label={delivered ? "Поставлено" : "В пути"}
          onClick={() => setField("is_delivered", !delivered)}
        >
          <span className="switch-thumb" aria-hidden />
        </button>
      </div>
    </div>
  );
}
