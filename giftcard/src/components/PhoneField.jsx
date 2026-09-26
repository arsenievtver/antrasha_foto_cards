import { formatPhoneMask } from "../utils/masks.js";

export default function PhoneField({ label, value, onChange, required = false }) {
  return (
    <label>
      {label}
      <input
        inputMode="tel"
        autoComplete="tel"
        placeholder="+7 (999) 123-45-67"
        value={value}
        onChange={(event) => onChange(formatPhoneMask(event.target.value))}
        required={required}
      />
    </label>
  );
}
