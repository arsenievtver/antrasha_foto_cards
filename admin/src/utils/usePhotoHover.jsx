import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Большой превью-оверлей фотографии при наведении курсора.
 *
 * Бесплатен по сети: показывает ту же `url`, что уже отрисована в сетке миниатюр —
 * браузер берёт картинку из своего кэша. Оверлей — один на странице, с
 * `pointer-events: none`, не мешает клику и hover-эффектам нижних элементов.
 *
 * Защита от моргания: показывается через HOVER_DELAY_MS после mouseenter; быстрая
 * пробежка курсора по сетке не успевает его открыть. На `mousedown` (например,
 * клик по карточке открывает модалку) — мгновенно скрывается.
 */
const HOVER_DELAY_MS = 1980;

export function useHoverPreview() {
  const [url, setUrl] = useState(null);
  const enterTimer = useRef(null);

  const clearTimer = useCallback(() => {
    if (enterTimer.current) {
      clearTimeout(enterTimer.current);
      enterTimer.current = null;
    }
  }, []);

  useEffect(() => () => clearTimer(), [clearTimer]);

  const showAfterDelay = useCallback(
    (u) => {
      clearTimer();
      enterTimer.current = setTimeout(() => setUrl(u), HOVER_DELAY_MS);
    },
    [clearTimer],
  );

  const hide = useCallback(() => {
    clearTimer();
    setUrl(null);
  }, [clearTimer]);

  /** Spread'ьте результат на элемент-триггер (например, `.photo-cell` или `<a>`). */
  const hoverProps = useCallback(
    (u) => ({
      onMouseEnter: () => showAfterDelay(u),
      onMouseLeave: hide,
      onMouseDown: hide,
    }),
    [showAfterDelay, hide],
  );

  const overlay = url ? (
    <div className="hover-preview" aria-hidden="true">
      <img src={url} alt="" draggable={false} />
    </div>
  ) : null;

  return { hoverProps, overlay };
}
