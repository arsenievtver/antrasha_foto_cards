import { useEffect, useRef } from "react";

export default function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder,
  busy,
}) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    function fit() {
      const probe = el.cloneNode(false);
      probe.value = el.value || el.placeholder || "";
      probe.rows = 1;
      probe.style.position = "absolute";
      probe.style.visibility = "hidden";
      probe.style.height = "auto";
      probe.style.maxHeight = "none";
      probe.style.width = `${el.offsetWidth}px`;
      probe.style.overflow = "hidden";
      el.parentElement?.appendChild(probe);
      el.style.height = `${probe.scrollHeight}px`;
      probe.remove();
    }

    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [value]);

  return (
    <form className="wh-ai__composer" onSubmit={onSubmit}>
      <textarea
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit(e);
          }
        }}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        {busy ? "…" : "Отправить"}
      </button>
    </form>
  );
}
