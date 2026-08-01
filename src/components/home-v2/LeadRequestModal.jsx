import { useState } from "react";
import { createFittingRequest, createGuestFittingRequest } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import PrivacyConsent from "../PrivacyConsent";
import { formatPhoneMask, normalizePhoneRu } from "../../utils/masks";
import "../../pages/ThankYou.css";
import "./LeadRequestModal.css";

export default function LeadRequestModal({ open, accent, onClose }) {
	const { isAuthenticated } = useAuth();
	const [phone, setPhone] = useState("");
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState("");
	const [done, setDone] = useState(false);

	if (!open) return null;

	async function onFittingRequest() {
		setErr("");
		setBusy(true);
		try {
			const accentNote = accent?.note ? `[${accent.note}] ` : "";
			const note = `${accentNote}Главная — акцент`.trim();
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

	function handleClose() {
		setPhone("");
		setErr("");
		setDone(false);
		onClose?.();
	}

	return (
		<div className="hv2-lead-backdrop" role="presentation" onClick={handleClose}>
			<div
				className="hv2-lead-modal"
				role="dialog"
				aria-modal
				aria-labelledby="hv2-lead-title"
				onClick={(ev) => ev.stopPropagation()}
			>
				<button
					type="button"
					className="hv2-lead-close"
					onClick={handleClose}
					aria-label="Закрыть"
				>
					×
				</button>

				<div className="thank-fitting hv2-lead-fitting">
					<p id="hv2-lead-title" className="thank-fitting-title">
						Персональная примерка в ANTRASHA
					</p>
					<p className="thank-fitting-text">
						{isAuthenticated
							? "Нажмите кнопку ниже — мы свяжемся с вами по номеру из профиля: уточним размеры и удобное время, подготовим образы под ваш вкус. Примерка в бутике в центре Твери или выезд с подборкой к вам домой или в офис."
							: "Укажите телефон и нажмите кнопку — перезвоним, чтобы согласовать время и формат примерки: в бутике на бульваре Радищева или выезд с подборкой к вам домой или в офис."}
					</p>

					{!isAuthenticated && !done ? (
						<>
							<label className="thank-label" htmlFor="hv2-lead-phone">
								Телефон
							</label>
							<input
								id="hv2-lead-phone"
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
							Заявка принята. Скоро позвоним для согласования примерки.
						</p>
					) : (
						<>
							<PrivacyConsent />
							<button
								type="button"
								className="thank-button thank-submit"
								disabled={busy}
								onClick={onFittingRequest}
							>
								{busy ? "Отправляем…" : "Заявка на примерку"}
							</button>
						</>
					)}
				</div>
			</div>
		</div>
	);
}
