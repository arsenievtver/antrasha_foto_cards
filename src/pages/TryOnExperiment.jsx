import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
	ensureSessionId,
	fetchTryOnCatalog,
	fetchTryOnStatus,
	runTryOnExperiment,
} from "../api/client";
import "./TryOnExperiment.css";

const GENDER_STORAGE_KEY = "tryon_experiment_gender";

function parseGenderParam(raw) {
	if (raw === "male" || raw === "female") return raw;
	return null;
}

function readStoredGender() {
	try {
		return parseGenderParam(localStorage.getItem(GENDER_STORAGE_KEY));
	} catch {
		return null;
	}
}

export default function TryOnExperiment() {
	const navigate = useNavigate();
	const [searchParams, setSearchParams] = useSearchParams();
	const urlGender = parseGenderParam(searchParams.get("gender"));
	const storedGender = readStoredGender();

	const [enabled, setEnabled] = useState(null);
	const [gender, setGender] = useState(urlGender ?? storedGender);
	const [catalog, setCatalog] = useState([]);
	const [catalogLoading, setCatalogLoading] = useState(true);
	const [selectedId, setSelectedId] = useState(null);
	const [personPreview, setPersonPreview] = useState(null);
	const [personFile, setPersonFile] = useState(null);
	const [busy, setBusy] = useState(false);
	const [err, setErr] = useState("");
	const [resultUrl, setResultUrl] = useState(null);
	const [elapsed, setElapsed] = useState(null);
	const fileRef = useRef(null);

	const loadCatalog = useCallback(async () => {
		setCatalogLoading(true);
		setErr("");
		try {
			const data = await fetchTryOnCatalog(gender);
			setCatalog(data.photos || []);
			setSelectedId(null);
		} catch (ex) {
			setErr(ex.message || "Не удалось загрузить образы");
			setCatalog([]);
		} finally {
			setCatalogLoading(false);
		}
	}, [gender]);

	useEffect(() => {
		let cancelled = false;
		(async () => {
			try {
				await ensureSessionId();
				const st = await fetchTryOnStatus();
				if (!cancelled) {
					setEnabled(st.enabled);
					if (!st.enabled) setErr(st.message || "Примерка недоступна");
				}
			} catch (ex) {
				if (!cancelled) {
					setEnabled(false);
					setErr(ex.message || "Ошибка загрузки");
				}
			}
		})();
		return () => {
			cancelled = true;
		};
	}, []);

	useEffect(() => {
		if (enabled && gender) loadCatalog();
	}, [gender, enabled, loadCatalog]);

	function pickGender(next) {
		setGender(next);
		setSelectedId(null);
		setResultUrl(null);
		setElapsed(null);
		try {
			localStorage.setItem(GENDER_STORAGE_KEY, next);
		} catch {
			/* private mode */
		}
		const nextParams = new URLSearchParams(searchParams);
		nextParams.set("gender", next);
		setSearchParams(nextParams, { replace: true });
	}

	function onPickPerson(file) {
		if (!file) return;
		setErr("");
		setResultUrl(null);
		setElapsed(null);
		if (personPreview) URL.revokeObjectURL(personPreview);
		setPersonFile(file);
		setPersonPreview(URL.createObjectURL(file));
	}

	async function onRun() {
		if (!personFile || !selectedId) return;
		setBusy(true);
		setErr("");
		setResultUrl(null);
		setElapsed(null);
		try {
			const data = await runTryOnExperiment({
				photoId: selectedId,
				personFile,
			});
			setResultUrl(data.result_url);
			setElapsed(data.elapsed_seconds);
		} catch (ex) {
			setErr(ex.message || "Не удалось выполнить примерку");
		} finally {
			setBusy(false);
		}
	}

	function resetExperiment() {
		setResultUrl(null);
		setElapsed(null);
		setSelectedId(null);
	}

	const selectedPhoto = catalog.find((p) => p.id === selectedId);

	return (
		<div className="tryon-page">
			<header className="tryon-topbar">
				<button
					type="button"
					className="tryon-back"
					onClick={() => navigate("/")}
					aria-label="На главную"
				>
					<span className="tryon-back__chevron" aria-hidden />
					назад
				</button>
				<span className="tryon-badge">эксперимент</span>
			</header>

			<main className="tryon-main">
				<h1 className="tryon-title">Примерка</h1>
				<p className="tryon-lead">
					Сначала выберите пол, затем своё фото и образ из каталога. Тестовая страница,
					~1 запрос к FASHN за попытку.
				</p>

				{enabled === false ? (
					<p className="tryon-error">{err || "Сервис выключен"}</p>
				) : null}

				{enabled ? (
					<>
						<section className="tryon-block tryon-block--gender">
							<h2 className="tryon-block__title">Кто примеряет?</h2>
							<p className="tryon-hint">
								От этого зависит каталог образов — мужской или женский.
							</p>
							<div className="tryon-gender-tabs tryon-gender-tabs--hero" role="tablist">
								<button
									type="button"
									role="tab"
									aria-selected={gender === "male"}
									className={
										gender === "male"
											? "tryon-gender-tab tryon-gender-tab--active"
											: "tryon-gender-tab"
									}
									onClick={() => pickGender("male")}
								>
									Мужчина
								</button>
								<button
									type="button"
									role="tab"
									aria-selected={gender === "female"}
									className={
										gender === "female"
											? "tryon-gender-tab tryon-gender-tab--active"
											: "tryon-gender-tab"
									}
									onClick={() => pickGender("female")}
								>
									Женщина
								</button>
							</div>
							{!gender ? (
								<p className="tryon-hint tryon-hint--emph">
									Выберите пол, чтобы открыть каталог образов.
								</p>
							) : null}
						</section>

						{gender ? (
						<>
						<section className="tryon-block">
							<h2 className="tryon-block__title">1. Ваше фото</h2>
							<p className="tryon-hint">
								В полный рост или по пояс, лицо хорошо видно, нейтральный фон — так
								результат обычно лучше.
							</p>
							<div className="tryon-person-row">
								{personPreview ? (
									<img
										src={personPreview}
										alt="Ваше фото"
										className="tryon-person-preview"
									/>
								) : (
									<div className="tryon-person-placeholder">нет фото</div>
								)}
								<div className="tryon-person-actions">
									<input
										ref={fileRef}
										type="file"
										accept="image/*"
										capture="user"
										className="tryon-file-input"
										onChange={(e) => {
											const f = e.target.files?.[0];
											onPickPerson(f);
											e.target.value = "";
										}}
									/>
									<button
										type="button"
										className="tryon-btn tryon-btn--secondary"
										onClick={() => fileRef.current?.click()}
									>
										Камера / галерея
									</button>
									{personPreview ? (
										<button
											type="button"
											className="tryon-btn tryon-btn--ghost"
											onClick={() => {
												if (personPreview) URL.revokeObjectURL(personPreview);
												setPersonPreview(null);
												setPersonFile(null);
											}}
										>
											Сбросить
										</button>
									) : null}
								</div>
							</div>
						</section>

						<section className="tryon-block">
							<h2 className="tryon-block__title">
								2. Образ из каталога
								<span className="tryon-block__subtitle">
									{gender === "male" ? "мужской" : "женский"}
								</span>
							</h2>
							{catalogLoading ? (
								<p className="tryon-hint">Загружаем образы…</p>
							) : (
								<div className="tryon-grid">
									{catalog.map((p) => (
										<button
											key={p.id}
											type="button"
											className={
												selectedId === p.id
													? "tryon-grid__item tryon-grid__item--selected"
													: "tryon-grid__item"
											}
											onClick={() => {
												setSelectedId(p.id);
												setResultUrl(null);
											}}
										>
											<img src={p.url} alt="" loading="lazy" />
										</button>
									))}
								</div>
							)}
							{selectedPhoto?.brand ? (
								<p className="tryon-hint">Выбрано: {selectedPhoto.brand}</p>
							) : null}
						</section>

						{resultUrl ? (
							<section className="tryon-block tryon-block--result">
								<h2 className="tryon-block__title">Результат</h2>
								{elapsed != null ? (
									<p className="tryon-hint">Готово за {elapsed} с</p>
								) : null}
								<img src={resultUrl} alt="Результат примерки" className="tryon-result" />
								<button
									type="button"
									className="tryon-btn tryon-btn--secondary"
									onClick={resetExperiment}
								>
									Попробовать другой образ
								</button>
							</section>
						) : (
							<div className="tryon-run-wrap">
								{err ? <p className="tryon-error">{err}</p> : null}
								<button
									type="button"
									className="tryon-btn tryon-btn--primary"
									disabled={busy || !personFile || !selectedId}
									onClick={onRun}
								>
									{busy ? "Генерируем… (до 2 мин)" : "Примерить на меня"}
								</button>
							</div>
						)}
						</>
						) : null}
					</>
				) : null}
			</main>
		</div>
	);
}
