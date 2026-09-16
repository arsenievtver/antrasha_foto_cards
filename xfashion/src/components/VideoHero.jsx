import { useEffect, useRef, useState } from "react";
import HeroHighlights from "./HeroHighlights.jsx";

const DEFAULT_DESKTOP_URL =
  "https://storage.yandexcloud.net/files-for-sites/Antrasha_AI_fashion_web_1080p.mp4";
const DESKTOP_URL = import.meta.env.VITE_XFASHION_VIDEO_URL || DEFAULT_DESKTOP_URL;
const MOBILE_URL = (import.meta.env.VITE_XFASHION_VIDEO_MOBILE_URL || "").trim();
const MOBILE_BREAKPOINT = "(max-width: 768px)";

function useNarrow() {
  const [narrow, setNarrow] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(MOBILE_BREAKPOINT).matches : false,
  );

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_BREAKPOINT);
    const sync = () => setNarrow(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  return narrow;
}

export default function VideoHero({ onCta, onPlayingChange }) {
  const videoRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const mobileSheet = useNarrow();
  const videoSrc = (mobileSheet && MOBILE_URL ? MOBILE_URL : DESKTOP_URL).trim();

  useEffect(() => {
    onPlayingChange?.(playing);
  }, [playing, onPlayingChange]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    setPlaying(false);
    el.pause();
    el.load();
  }, [videoSrc]);

  useEffect(() => {
    document.body.classList.toggle("xf-hero-fs", playing);
    return () => document.body.classList.remove("xf-hero-fs");
  }, [playing]);

  async function playVideo() {
    const el = videoRef.current;
    if (!el) return;
    try {
      if (el.readyState < 2) el.load();
      el.muted = false;
      el.loop = false;
      el.currentTime = 0;
      await el.play();
      setPlaying(true);
    } catch {
      /* браузер отклонил play */
    }
  }

  function stopVideo() {
    const el = videoRef.current;
    if (el) el.pause();
    setPlaying(false);
  }

  return (
    <section
      className={["xf-hero", mobileSheet ? "xf-hero--mobile-sheet" : "", playing ? "xf-hero--playing" : ""]
        .filter(Boolean)
        .join(" ")}
      aria-labelledby="xf-hero-title"
    >
      <div className="xf-hero__media">
        <video
          ref={videoRef}
          className="xf-hero__video"
          src={videoSrc}
          playsInline
          preload="auto"
          onEnded={stopVideo}
          onClick={playing ? stopVideo : undefined}
        />
        <div className={`xf-hero__scrim ${playing ? "xf-hero__scrim--hidden" : ""}`} />
        {!playing ? (
          <button
            type="button"
            className="xf-hero__play xf-hero__play-in"
            onClick={playVideo}
            aria-label="Смотреть презентацию Xfashion"
          >
            <span className="xf-hero__play-ring" aria-hidden="true">
              <svg className="xf-hero__play-icon" viewBox="0 0 24 24" width="32" height="32" aria-hidden>
                <path fill="currentColor" d="M8 5.14v13.72L19 12 8 5.14z" />
              </svg>
            </span>
            <span className="xf-hero__play-label">1 мин</span>
          </button>
        ) : (
          <button type="button" className="xf-hero__fs-hit" onClick={stopVideo} aria-label="Остановить видео" />
        )}
      </div>

      <div className={`xf-hero__content ${playing ? "xf-hero__content--playing" : ""}`}>
        <div className="xf-hero__copy">
          <p className="xf-eyebrow xf-hero__eyebrow xf-hero__anim xf-hero__anim--0">
            Готовое решение для магазинов одежды
          </p>
          <h1 id="xf-hero-title" className="xf-hero__title xf-hero__anim xf-hero__anim--1">
            <span className="xf-hero__title-line xf-hero__title-line--accent">Стильный lookbook</span>
            <span className="xf-hero__title-line">из&nbsp;фото с&nbsp;телефона и</span>
            <span className="xf-hero__title-line">Своё приложение</span>
            <span className="xf-hero__title-line">для&nbsp;клиентов</span>
          </h1>
          <p className="xf-hero__tagline xf-hero__anim xf-hero__anim--2">
            Без фотостудии и&nbsp;навыков — от&nbsp;5&nbsp;000&nbsp;₽/мес, оплата в&nbsp;рублях.
          </p>
          <div className="xf-hero__actions xf-hero__anim xf-hero__anim--3">
            <button type="button" className="xf-btn xf-btn--pill" onClick={onCta}>
              <span>Запросить демо</span>
              <span className="xf-btn__arrow" aria-hidden="true">
                →
              </span>
            </button>
          </div>
          {mobileSheet ? (
            <div className="xf-hero__anim xf-hero__anim--4">
              <HeroHighlights />
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
