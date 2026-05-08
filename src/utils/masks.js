/** Оставляем только цифры */
export function digitsOnly(s) {
	return String(s || "").replace(/\D/g, "");
}

/**
 * Маска телефона РФ: +7 (XXX) XXX-XX-XX
 * Ввод нормализуем к 11 цифрам 7XXXXXXXXXX для API.
 */
export function formatPhoneMask(raw) {
	const rawDigits = digitsOnly(raw);
	if (!rawDigits) return "";
	let d = rawDigits;
	if (d.startsWith("8")) d = "7" + d.slice(1);
	if (d.startsWith("9") && d.length <= 10) d = "7" + d;
	if (!d.startsWith("7")) d = "7" + d.replace(/^7+/, "");
	d = d.slice(0, 11);

	const rest = d.slice(1);
	let out = "+7";
	if (rest.length === 0) return out;
	out += " (" + rest.slice(0, 3);
	if (rest.length <= 3) return out;
	out += ") " + rest.slice(3, 6);
	if (rest.length <= 6) return out;
	out += "-" + rest.slice(6, 8);
	if (rest.length <= 8) return out;
	out += "-" + rest.slice(8, 10);
	return out;
}

/** Возвращает номер для API, например +79001234567, или null */
export function normalizePhoneRu(masked) {
	let d = digitsOnly(masked);
	if (d.startsWith("8")) d = "7" + d.slice(1);
	if (d.startsWith("9") && d.length === 10) d = "7" + d;
	if (d.length === 11 && d.startsWith("7")) return "+" + d;
	return null;
}

/** PIN как XXX-XXX (6 цифр) */
export function formatPinMask(raw) {
	const d = digitsOnly(raw).slice(0, 6);
	if (d.length <= 3) return d;
	return d.slice(0, 3) + "-" + d.slice(3);
}

export function pinDigits(masked) {
	return digitsOnly(masked).slice(0, 6);
}

/**
 * PIN до 12 цифр (админка user): XXX-XXX или XXX-XXX-XXXXXX.
 */
export function formatPinMaskUpTo12(raw) {
	const d = digitsOnly(raw).slice(0, 12);
	if (d.length === 0) return "";
	if (d.length <= 3) return d;
	if (d.length <= 6) return `${d.slice(0, 3)}-${d.slice(3)}`;
	return `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}`;
}

export function pinDigitsUpTo12(masked) {
	return digitsOnly(masked).slice(0, 12);
}
