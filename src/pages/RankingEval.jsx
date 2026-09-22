import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { fetchRankingEvalActive, submitRankingEval } from "../api/client";
import { useAuth } from "../context/AuthContext";
import "./RankingEval.css";

export default function RankingEval() {
	const { profile, token, loading: authLoading } = useAuth();
	const navigate = useNavigate();
	const [gender, setGender] = useState("female");
	const [data, setData] = useState(null);
	const [order, setOrder] = useState([]);
	const [err, setErr] = useState("");
	const [loading, setLoading] = useState(true);
	const [busy, setBusy] = useState(false);
	const [done, setDone] = useState(false);

	const load = useCallback(async () => {
		setLoading(true);
		setErr("");
		try {
			const d = await fetchRankingEvalActive(gender);
			setData(d);
			setOrder((d.photos || []).map((p) => p.photo_id));
			setDone(Boolean(d.already_submitted));
		} catch (ex) {
			setData(null);
			setOrder([]);
			setErr(ex.message || String(ex));
		} finally {
			setLoading(false);
		}
	}, [gender]);

	useEffect(() => {
		if (token && profile?.ranking_eval_enabled) load();
	}, [token, profile, load]);

	if (authLoading) {
		return <p className="ranking-eval-meta">Загрузка…</p>;
	}
	if (!token) {
		return <Navigate to="/" replace />;
	}
	if (!profile?.ranking_eval_enabled) {
		return (
			<div className="ranking-eval-page">
				<p className="ranking-eval-meta">Оценка подборки недоступна для этого аккаунта.</p>
				<Link to="/">На главную</Link>
			</div>
		);
	}

	function move(idx, dir) {
		setOrder((prev) => {
			const next = [...prev];
			const j = idx + dir;
			if (j < 0 || j >= next.length) return prev;
			[next[idx], next[j]] = [next[j], next[idx]];
			return next;
		});
	}

	async function onSubmit() {
		if (!data?.benchmark_id || busy || done) return;
		setBusy(true);
		setErr("");
		try {
			await submitRankingEval({
				benchmarkId: data.benchmark_id,
				humanOrder: order,
			});
			setDone(true);
		} catch (ex) {
			setErr(ex.message || String(ex));
		} finally {
			setBusy(false);
		}
	}

	const byId = Object.fromEntries((data?.photos || []).map((p) => [p.photo_id, p]));

	return (
		<div className="ranking-eval-page">
			<header className="ranking-eval-head">
				<p className="ranking-eval-back">
					<Link to="/">← Главная</Link>
				</p>
				<div className="ranking-eval-head-row">
					<h1 className="ranking-eval-title">Оценить подборку</h1>
					<label className="ranking-eval-toolbar">
						<select value={gender} onChange={(e) => setGender(e.target.value)} disabled={busy}>
							<option value="female">Женская</option>
							<option value="male">Мужская</option>
						</select>
					</label>
				</div>
				<p className="ranking-eval-meta">Сверху — то, что нравится больше.</p>
			</header>

			{loading ? <p className="ranking-eval-meta">Загрузка набора…</p> : null}
			{err ? <p className="ranking-eval-error">{err}</p> : null}

			{done ? (
				<div className="ranking-eval-done">
					<p>Спасибо! Оценка сохранена.</p>
					<button type="button" className="thank-button" onClick={() => navigate("/")}>
						На главную
					</button>
				</div>
			) : null}

			{!loading && !done && data ? (
				<>
					<ul className="ranking-eval-list">
						{order.map((pid, idx) => {
							const p = byId[pid];
							if (!p) return null;
							return (
								<li key={pid} className="ranking-eval-item">
									<img src={p.url} alt="" className="ranking-eval-photo" />
									<span className="ranking-eval-rank">{idx + 1}</span>
									<div className="ranking-eval-actions">
										<button
											type="button"
											aria-label="Выше"
											disabled={idx === 0 || busy}
											onClick={() => move(idx, -1)}
										>
											↑
										</button>
										<button
											type="button"
											aria-label="Ниже"
											disabled={idx === order.length - 1 || busy}
											onClick={() => move(idx, 1)}
										>
											↓
										</button>
									</div>
								</li>
							);
						})}
					</ul>
					<div className="ranking-eval-footer">
						<button type="button" className="thank-button ranking-eval-submit" disabled={busy} onClick={onSubmit}>
							{busy ? "Отправка…" : "Отправить"}
						</button>
					</div>
				</>
			) : null}
		</div>
	);
}
