/** Бэкенд отдаёт Decimal строками ("1234.56") — приводим к числу перед выводом. */
export function num(value) {
  if (value === null || value === undefined || value === "") return 0;
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function format(value, fractionDigits) {
  return num(value).toLocaleString("ru-RU", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

export function eur(value) {
  return `${format(value, 2)} €`;
}

export function rub(value) {
  if (value === null || value === undefined || value === "") return "—";
  return `${format(value, 2)} ₽`;
}

export function kg(value) {
  if (value === null || value === undefined || value === "") return "—";
  return `${format(value, 3)} кг`;
}

export function rate(value) {
  if (value === null || value === undefined || value === "") return "—";
  return format(value, 4);
}

export function dateRu(value) {
  if (!value) return "—";
  const [y, m, d] = String(value).split("-");
  if (!y || !m || !d) return String(value);
  return `${d}.${m}.${y}`;
}

/** Отрицательный остаток = переплата/переотгрузка, подсвечиваем иначе. */
export function balanceStyle(value) {
  const n = num(value);
  if (n > 0) return { color: "var(--danger, #c2410c)" };
  if (n < 0) return { color: "var(--muted)" };
  return undefined;
}

export const GENDER_LABELS = {
  men: "Мужской",
  women: "Женский",
  mixed: "Смешанный",
  unisex: "Универсальный",
};

export function genderLabel(value) {
  return GENDER_LABELS[value] || "—";
}

export const PAYMENT_KIND_LABELS = {
  prepayment: "Предоплата",
  main: "Основная",
};

export function paymentKindLabel(value) {
  return PAYMENT_KIND_LABELS[value] || value || "—";
}
