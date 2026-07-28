import { useState } from "react";
import { createBrand } from "../api.js";

export default function BrandModal({ onClose, onCreated }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    setErr("");
    try {
      const brand = await createBrand(trimmed);
      onCreated(brand);
      onClose();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal-sheet" onClick={(e) => e.stopPropagation()}>
        <h3>Новый бренд</h3>
        <form className="form-stack" onSubmit={onSubmit}>
          <label>
            Название
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Например, Brunello"
              autoFocus
              required
            />
          </label>
          {err ? <p className="error">{err}</p> : null}
          <div className="modal-actions">
            <button type="button" className="secondary" onClick={onClose} disabled={busy}>
              Отмена
            </button>
            <button type="submit" disabled={busy || !name.trim()}>
              {busy ? "…" : "Добавить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
