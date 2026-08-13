import { useEffect, useRef, useState } from "react";
import { createFittingRequest, createGuestFittingRequest, fetchModalVideo } from "../api/client";
import { useAuth } from "../context/AuthContext";
import PrivacyConsent from "./PrivacyConsent";
import { formatPhoneMask, normalizePhoneRu } from "../utils/masks";
import "../pages/ThankYou.css";
import "./VideoModal.css";

function withCacheBust(url, updatedAt) {
	if (!url) return url;
	if (!updatedAt) return url;
	const t = new Date(updatedAt).getTime();
	if (!Number.isFinite(t)) return url;
	const sep = url.includes("?") ? "&" : "?";
	return `${url}${sep}v=${t}`;
}

export default function VideoModal({ slug, onClose }) {
	const { isAuthenticated } = useAuth();
	const videoRef = useRef(null);
	const [payload, setPayload] = useState(null);
	const [loading, setLoading] = useState(false);
	const [loadErr, setLoadErr] = useState("");
	const [phone, setPhone] = useState("");
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState("");
	const [done, setDone] = useState(false);

	useEffect(() => {
		if (!slug) {
			setPayload(null);
			setLoadErr("");
			setLoading(false);
			return undefined;
		}
		let cancelled = false;
		setLoading(true);
		setLoadErr("");
		setPayload(null);
		setPhone("");
		setErr("");
		setDone(false);
		(async () => {
			try {
				const data = await fetchModalVideo(slug);
				if (!cancelled) setPayload(data);
			} catch (ex) {
				if (!cancelled) setLoadErr(ex.message || "Видео недоступно");
			} finally {
				if (!cancelled) setLoading(false);
			}
		})();
		return () => {
			cancelled = true;
		};
	}, [slug]);

	useEffect(() => {
		if (!slug) return undefined;
		const prev = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		const onKey = (e) => {
			if (e.key === "Escape") onClose?.();
		};
		window.addEventListener("keydown", onKey);
		return () => {
			document.body.style.overflow = prev;
			window.removeEventListener("keydown", onKey);
			const el = videoRef.current;
			if (el) {
				el.pause();
				el.removeAttribute("src");
				el.load();
			}
		};
	}, [slug, onClose]);

	useEffect(() => {
		if (!payload?.video_url || !videoRef.current) return;
		videoRef.current.play().catch(() => {});
	}, [payload?.video_url]);

	if (!slug) return null;

	const videoSrc = withCacheBust(payload?.video_url, payload?.updated_at);
	const posterSrc = withCacheBust(payload?.poster_url, payload?.updated_at);
	const isLead = payload?.cta_mode === "lead";
	const ctaLabel =
		(payload?.cta_label || "").trim() || (isLead ? "Оставить заявку" : "Закрыть");

	async function onLead() {
		setErr("");
		setBusy(true);
		try {
			const note = (payload?.lead_note || "").trim() || `Видео: ${payload?.title || slug}`;
			if (isAuthenticated) {
				await createFittingRequest({
					likes: 0,
					total: 0,
					photoIds: [],
					note,
				});
			} else {
				const norm = normalizePhoneRu(phone);
				if (!norm) {
					setErr("Укажите корректный номер телефона");
					return;
				}
				await createGuestFittingRequest({ phone: norm, note });
			}
			setDone(true);
		} catch (ex) {
			setErr(ex.message || "Не удалось отправить заявку");
		} finally {
			setBusy(false);
		}
	}

	return (
		<div className="video-modal" role="presentation" onClick={onClose}>
			<div
				className="video-modal__panel"
				role="dialog"
				aria-modal
				aria-labelledby="video-modal-title"
				onClick={(e) => e.stopPropagation()}
			>
				<button
					type="button"
					className="video-modal__close"
					onClick={onClose}
					aria-label="Закрыть"
				>
					×
				</button>

				{loading ? (
					<p className="video-modal__status">Загрузка…</p>
				) : loadErr ? (
					<p className="video-modal__status">{loadErr}</p>
				) : payload ? (
					<>
						<div className="video-modal__player">
							<video
								ref={videoRef}
								className="video-modal__video"
								src={videoSrc}
								poster={posterSrc || undefined}
								controls
								playsInline
								preload="metadata"
							/>
						</div>
						<div className="video-modal__after">
							<h2 id="video-modal-title" className="video-modal__title">
								{payload.title}
							</h2>
							{payload.body ? (
								<p className="video-modal__body">{payload.body}</p>
							) : null}

							{isLead ? (
								<div className="thank-fitting video-modal__fitting">
									{!isAuthenticated && !done ? (
										<>
											<label className="thank-label" htmlFor="video-modal-phone">
												Телефон
											</label>
											<input
												id="video-modal-phone"
												className="thank-input"
												inputMode="tel"
												autoComplete="tel"
												placeholder="+7 (999) 123-45-67"
												value={phone}
												onChange={(e) => setPhone(formatPhoneMask(e.target.value))}
											/>
										</>
									) : null}
									{err ? <p className="thank-error">{err}</p> : null}
									{done ? (
										<p className="thank-note thank-success">
											Заявка принята. Скоро свяжемся с вами.
										</p>
									) : (
										<>
											<PrivacyConsent />
											<button
												type="button"
												className="thank-button thank-submit"
												disabled={busy}
												onClick={onLead}
											>
												{busy ? "Отправляем…" : ctaLabel}
											</button>
										</>
									)}
								</div>
							) : (
								<button type="button" className="video-modal__dismiss" onClick={onClose}>
									{ctaLabel}
								</button>
							)}
						</div>
					</>
				) : null}
			</div>
		</div>
	);
}
