import { useCallback, useEffect, useState } from "react";
import {
  apiUrl,
  createMcpKey,
  fetchMyMcpKey,
  revokeMcpKey,
  rotateMcpKey,
} from "../api.js";

function formatDate(value) {
  if (!value) return null;
  return new Date(value).toLocaleString("ru-RU");
}

function mcpEndpoint() {
  const path = apiUrl("/mcp");
  if (path.startsWith("http")) return path;
  return `${window.location.origin}${path}`;
}

function cursorSnippet(endpoint, key) {
  return JSON.stringify(
    {
      mcpServers: {
        "antrasha-procurement": {
          url: endpoint,
          headers: {
            Authorization: `Bearer ${key || "mcp_live_…"}`,
          },
        },
      },
    },
    null,
    2,
  );
}

export default function McpKey() {
  const [key, setKey] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState("");
  const [confirming, setConfirming] = useState(null);
  const [writeScope, setWriteScope] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      setKey(await fetchMyMcpKey());
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const accept = (data) => {
    setKey(data);
    setCopied("");
    setConfirming(null);
  };

  const create = async () => {
    setBusy(true);
    setErr("");
    try {
      accept(
        await createMcpKey({
          name: "MCP клиент",
          scope: writeScope ? "write" : "read",
        }),
      );
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const rotate = async () => {
    setBusy(true);
    setErr("");
    try {
      accept(await rotateMcpKey(key.id));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    setErr("");
    try {
      await revokeMcpKey(key.id);
      setKey(null);
      setConfirming(null);
      setCopied("");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const copyText = async (label, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
    } catch {
      setErr("Не удалось скопировать — выделите текст и скопируйте вручную");
    }
  };

  const endpoint = mcpEndpoint();

  const renderKey = () => {
    if (loading) return <p className="mcp-key-hint">Загрузка…</p>;

    if (!key) {
      return (
        <>
          <p className="mcp-key-hint">
            Ключ не выпущен. Он нужен, чтобы подключить ИИ-клиента к закупкам:
            сезоны, бренды, заказы, оплаты, поставки и курс EUR.
          </p>
          <label className="mcp-key-scope">
            <input
              type="checkbox"
              checked={writeScope}
              onChange={(e) => setWriteScope(e.target.checked)}
            />
            <span>
              Разрешить изменять данные — ИИ сможет создавать и править записи.
              Удаление через ИИ недоступно в любом случае. Без галочки ключ только читает.
            </span>
          </label>
          <div className="mcp-key-actions">
            <button type="button" disabled={busy} onClick={create}>
              Создать ключ
            </button>
          </div>
        </>
      );
    }

    if (confirming) {
      const isRotate = confirming === "rotate";
      return (
        <>
          <p className="mcp-key-warning">
            {isRotate
              ? "Текущий ключ перестанет работать сразу, ИИ-клиента придётся перенастроить на новый. Права нового ключа останутся прежними. Продолжить?"
              : "Текущий ключ перестанет работать сразу, новый выписан не будет. Продолжить?"}
          </p>
          <div className="mcp-key-actions">
            <button type="button" disabled={busy} onClick={isRotate ? rotate : revoke}>
              {isRotate ? "Да, обновить" : "Да, отозвать"}
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => setConfirming(null)}
            >
              Отмена
            </button>
          </div>
        </>
      );
    }

    return (
      <>
        <div className="mcp-key-value">{key.key || key.masked_key}</div>
        {!key.key && (
          <p className="mcp-key-hint">
            Значение ключа не сохранено. Обновите его, чтобы увидеть текст целиком.
          </p>
        )}
        <p className={key.scope === "write" ? "mcp-key-warning" : "mcp-key-hint"}>
          {key.scope === "write"
            ? "Права: чтение и изменение. Удаление по-прежнему только вручную в админке."
            : "Права: только чтение. Чтобы ИИ мог создавать и править записи, отзовите ключ и выпустите новый с галочкой."}
        </p>
        <p className="mcp-key-hint">
          {key.last_used_at
            ? `Последнее использование: ${formatDate(key.last_used_at)}`
            : "Ещё ни разу не использовался"}
        </p>
        <div className="mcp-key-actions">
          {key.key && (
            <button type="button" onClick={() => copyText("key", key.key)}>
              {copied === "key" ? "Скопировано" : "Скопировать"}
            </button>
          )}
          <button type="button" className="secondary" onClick={() => setConfirming("rotate")}>
            Обновить
          </button>
          <button type="button" className="danger" onClick={() => setConfirming("revoke")}>
            Отозвать
          </button>
        </div>
      </>
    );
  };

  return (
    <div className="card mcp-key">
      <h2 style={{ marginTop: 0 }}>Ключ для ИИ (MCP)</h2>
      <p className="mcp-key-hint">
        Отдельный сервер закупок этого проекта. МойСклад он не заменяет и к нему не
        подключается. Эндпоинт: <code>{endpoint}</code>
      </p>
      {renderKey()}
      {err && <p className="error">{err}</p>}

      <h3>Подключение клиента</h3>
      <p className="mcp-key-hint">
        Заголовок <code>Authorization: Bearer …</code>. Пример для Cursor:
      </p>
      <pre className="mcp-key-value">{cursorSnippet(endpoint, key?.key)}</pre>
      <div className="mcp-key-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => copyText("snippet", cursorSnippet(endpoint, key?.key))}
        >
          {copied === "snippet" ? "Скопировано" : "Скопировать конфиг"}
        </button>
      </div>
    </div>
  );
}
