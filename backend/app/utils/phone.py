import re


def normalize_ru_phone(phone: str) -> str | None:
	"""Нормализация к виду +7XXXXXXXXXX для РФ. None если формат не подходит."""
	d = re.sub(r"\D", "", (phone or "").strip())
	if not d:
		return None
	if d.startswith("8") and len(d) == 11:
		d = "7" + d[1:]
	if len(d) == 10 and d.startswith("9"):
		d = "7" + d
	if len(d) == 11 and d.startswith("7"):
		return f"+{d}"
	return None
