import { useEffect, useRef, useState } from "react";
import { createMyFeedback, fetchMyFeedback, updateMyFeedback } from "../api.js";

function timeLabel(iso) {
  return new Date(iso).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

export default function Feedback() {
  const [items, setItems] = useState([]);
  const [input, setInput] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchMyFeedback();
        if (!cancelled) setItems(Array.isArray(data) ? data : []);
      } catch (e) {
        if (!cancelled) setErr(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    function onVisibility() {
      if (document.visibilityState === "visible") load();
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  useEffect(() => {
    if (!editingId) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [items, editingId]);

  function startEdit(item) {
    setEditingId(item.id);
    setInput(item.text);
    setErr("");
    inputRef.current?.focus();
  }

  function cancelEdit() {
    setEditingId(null);
    setInput("");
  }

  async function onSubmit(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    setErr("");
    try {
      if (editingId) {
        const updated = await updateMyFeedback(editingId, text);
        setItems((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
        setEditingId(null);
      } else {
        const created = await createMyFeedback(text);
        setItems((prev) => [...prev, created]);
      }
      setInput("");
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="muted">Загрузка…</p>;

  return (
    <div className="wh-ai feedback">
      <p className="muted small" style={{ margin: 0 }}>
        Что спрашивали, а у нас нет; каких размеров не хватило; какие бренды и вещи ищут
        клиенты. Пишите как есть. Здесь видны только ваши сообщения за сегодня — в полночь
        чат очищается, но всё отправленное сохраняется.
      </p>

      {err ? <p className="error">{err}</p> : null}

      <section className="outlet-card wh-ai__chat">
        {items.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Сегодня пока пусто. Например: «Спрашивали мужские джинсы Acne 34/32 — нет размера».
          </p>
        ) : (
          <div className="wh-ai__thread feedback__thread">
            {items.map((item) => (
              <div
                key={item.id}
                className={`wh-ai-msg wh-ai-msg--user${
                  editingId === item.id ? " feedback__msg--editing" : ""
                }`}
              >
                <div className="wh-ai-msg__body wh-ai-msg__body--plain">{item.text}</div>
                <div className="wh-ai-msg__meta muted feedback__meta">
                  <span>
                    {timeLabel(item.created_at)}
                    {item.updated_at ? " · изменено" : ""}
                  </span>
                  <button
                    type="button"
                    className="feedback__edit"
                    disabled={busy}
                    onClick={() => startEdit(item)}
                  >
                    Изменить
                  </button>
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}

        <form className="wh-ai__composer" onSubmit={onSubmit}>
          <textarea
            ref={inputRef}
            rows={3}
            value={input}
            maxLength={4000}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Что спрашивали, а у нас нет?"
            disabled={busy}
          />
          <div className="feedback__actions">
            {editingId ? (
              <button type="button" className="secondary" disabled={busy} onClick={cancelEdit}>
                Отмена
              </button>
            ) : null}
            <button type="submit" disabled={busy || !input.trim()}>
              {busy ? "…" : editingId ? "Сохранить" : "Отправить"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
