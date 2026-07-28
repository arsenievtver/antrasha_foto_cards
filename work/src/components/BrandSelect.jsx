import { useState } from "react";
import BrandModal from "./BrandModal.jsx";

/** Селект бренда + кнопка «+» для быстрого добавления. */
export default function BrandSelect({ brands, value, onChange, onBrandsChange, required }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <label>
        Бренд
        <div className="brand-field">
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            required={required}
          >
            <option value="">— выберите —</option>
            {(brands || []).map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn-plus secondary"
            title="Добавить бренд"
            onClick={() => setOpen(true)}
          >
            +
          </button>
        </div>
      </label>
      {open ? (
        <BrandModal
          onClose={() => setOpen(false)}
          onCreated={(brand) => {
            onBrandsChange?.([...(brands || []), brand].sort((a, b) =>
              a.name.localeCompare(b.name, "ru"),
            ));
            onChange(brand.id);
          }}
        />
      ) : null}
    </>
  );
}
