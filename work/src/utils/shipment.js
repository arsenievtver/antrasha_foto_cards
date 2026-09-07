/** Статус поставки для бейджей в списке и карточке. */
export function shipmentStatusMeta(isDelivered) {
  return isDelivered
    ? { label: "Поставлено", tone: "ok" }
    : { label: "В пути", tone: "warn" };
}
