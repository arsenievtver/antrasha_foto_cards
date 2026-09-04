import { useCallback, useEffect, useState } from "react";
import { broadcastPush, fetchPushStats } from "../api.js";

const AUDIENCES = [
  { value: "all", label: "Всем подписчикам" },
  { value: "male", label: "Мужское + обе категории" },
  { value: "female", label: "Женское + обе категории" },
  { value: "both", label: "Только «обе категории»" },
];

const URL_PRESETS = [
  { value: "", label: "Авто (по подписке: swipe / главная)" },
  { value: "/", label: "Главная /" },
  { value: "/swipe/male", label: "Свайп — мужское" },
  { value: "/swipe/female", label: "Свайп — женское" },
];

export default function PushNotifications() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("Новые образы — оцените новинки");
  const [urlPreset, setUrlPreset] = useState("");
  const [urlCustom, setUrlCustom] = useState("");
  const [audience, setAudience] = useState("all");
  const [respectCooldown, setRespectCooldown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const reload = useCallback(async () => {
    const data = await fetchPushStats();
    setStats(data);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await reload();
      } catch (e) {
        if (!cancelled) setErr(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reload]);

  async function handleSend(e) {
    e.preventDefault();
    setErr("");
    setResult(null);
    const url = (urlCustom.trim() || urlPreset || "").trim() || null;
    if (!window.confirm("Отправить push всем подходящим подписчикам?")) return;
    setBusy(true);
    try {
      const data = await broadcastPush({
        title: title.trim(),
        body: body.trim(),
        url,
        audience,
        respect_cooldown: respectCooldown,
      });
      setResult(data);
      await reload();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p>Загрузка…</p>;

  return (
    <div>
      <h1>Push-уведомления</h1>
      <p className="muted" style={{ maxWidth: "40rem" }}>
        Ручная рассылка подписчикам PWA. Авто-уведомления при загрузке фото
        отключены — чтобы не спамить при пакетных выгрузках. Когда партия готова —
        отправьте отсюда.
      </p>

      {err ? (
        <p className="error" style={{ marginTop: "1rem" }}>
          {err}
        </p>
      ) : null}

      <section className="card" style={{ marginTop: "1.25rem", maxWidth: "40rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>Подписчики</h2>
        {!stats?.configured ? (
          <p className="error">
            Web Push не настроен на сервере (нужны VAPID_PUBLIC_KEY,
            VAPID_PRIVATE_KEY, VAPID_CLAIMS_SUB).
          </p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.6 }}>
            <li>
              Активных: <strong>{stats.active_total}</strong>
            </li>
            <li>Мужское: {stats.active_male}</li>
            <li>Женское: {stats.active_female}</li>
            <li>Обе категории: {stats.active_both}</li>
          </ul>
        )}
      </section>

      <form
        className="card form-stack"
        style={{ marginTop: "1.25rem", maxWidth: "40rem" }}
        onSubmit={handleSend}
      >
        <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>Отправить</h2>

        <label>
          Заголовок (необязательно)
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={80}
            placeholder="Пусто — на iPhone возьмётся первая строка текста"
          />
          <span className="muted" style={{ display: "block", marginTop: "0.35rem" }}>
            Не пишите «ANTRASHA»: на iPhone под заголовком и так будет «from
            ANTRASHA».
          </span>
        </label>

        <label>
          Текст
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={200}
            rows={3}
            required
          />
        </label>

        <label>
          Аудитория
          <select value={audience} onChange={(e) => setAudience(e.target.value)}>
            {AUDIENCES.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Куда вести по клику
          <select
            value={urlPreset}
            onChange={(e) => {
              setUrlPreset(e.target.value);
              if (e.target.value) setUrlCustom("");
            }}
          >
            {URL_PRESETS.map((u) => (
              <option key={u.label} value={u.value}>
                {u.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Свой URL (опционально, перекрывает пресет)
          <input
            value={urlCustom}
            onChange={(e) => setUrlCustom(e.target.value)}
            placeholder="/swipe/female или https://…"
          />
        </label>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            marginTop: "0.75rem",
          }}
        >
          <input
            type="checkbox"
            checked={respectCooldown}
            onChange={(e) => setRespectCooldown(e.target.checked)}
          />
          Не слать тем, кому уже писали за последние 24 часа
        </label>

        <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem" }}>
          <button type="submit" disabled={busy || !stats?.configured}>
            {busy ? "Отправляем…" : "Отправить push"}
          </button>
        </div>

        {result ? (
          <p style={{ marginTop: "1rem" }}>
            Готово: eligible {result.eligible}, отправлено{" "}
            <strong>{result.sent}</strong>, ошибок {result.failed}, пропущено{" "}
            {result.skipped}.
          </p>
        ) : null}
      </form>

      <section style={{ marginTop: "1.5rem", maxWidth: "40rem" }}>
        <h2 style={{ fontSize: "1.05rem" }}>Как проверить</h2>
        <ol style={{ lineHeight: 1.55, paddingLeft: "1.2rem" }}>
          <li>
            На телефоне откройте сайт в браузере (или уже установленный PWA).
          </li>
          <li>
            Включите уведомления: колокольчик на главной или баннер на свайпе.
            На iPhone push работает надёжнее из ярлыка «на экран Домой».
          </li>
          <li>
            Убедитесь, что счётчик «Активных» выше вырос, затем отправьте тестовый
            push с этой страницы.
          </li>
          <li>
            Сверните приложение / заблокируйте экран — уведомление должно прийти
            в шторку.
          </li>
        </ol>
      </section>
    </div>
  );
}
