import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchActiveHeroBanners } from "../api/client.js";
import { useAuth } from "../context/AuthContext";
import UserMenu from "../components/UserMenu";
import { isPushSubscribedLocally } from "../push/notifications.js";
import AccentBlocks from "../components/home-v2/AccentBlocks";
import BrandMarquee from "../components/home-v2/BrandMarquee";
import GenderCards from "../components/home-v2/GenderCards";
import HeroBanner from "../components/home-v2/HeroBanner";
import HomeBottomBar from "../components/home-v2/HomeBottomBar";
import LeadRequestModal from "../components/home-v2/LeadRequestModal";
import NotifySettingsModal from "../components/home-v2/NotifySettingsModal";
import { HOME_V2_DEFAULT_HERO } from "../components/home-v2/homeV2Constants";
import logoMark from "../assets/image/logo-a-transparent.png";
import "./HomeV2.css";

export default function HomeV2() {
	const navigate = useNavigate();
	const { profile } = useAuth();
	const [heroes, setHeroes] = useState([HOME_V2_DEFAULT_HERO]);
	const [userOpen, setUserOpen] = useState(false);
	const [notifyOpen, setNotifyOpen] = useState(false);
	const [leadOpen, setLeadOpen] = useState(false);
	const [leadAccent, setLeadAccent] = useState(null);
	const [hasPush, setHasPush] = useState(() => isPushSubscribedLocally());

	useEffect(() => {
		let cancelled = false;
		(async () => {
			try {
				const data = await fetchActiveHeroBanners();
				const items = Array.isArray(data?.items) ? data.items : [];
				const withMedia = items.filter(
					(s) => s?.image_url || s?.image_url_desktop,
				);
				if (!cancelled) {
					setHeroes(
						withMedia.length > 0 ? withMedia : [HOME_V2_DEFAULT_HERO],
					);
				}
			} catch {
				if (!cancelled) setHeroes([HOME_V2_DEFAULT_HERO]);
			}
		})();
		return () => {
			cancelled = true;
		};
	}, []);

	useEffect(() => {
		if (!notifyOpen) setHasPush(isPushSubscribedLocally());
	}, [notifyOpen]);

	const userInitial =
		profile?.display_name?.trim()?.[0] ||
		profile?.phone?.replace(/\D/g, "")?.slice(-1) ||
		"";

	return (
		<div className="hv2-page">
			<header className="hv2-header">
				<div className="hv2-brand">
					<img src={logoMark} alt="" className="hv2-brand__mark" />
					<div className="hv2-brand__text">
						<span className="hv2-brand__name">ANTRASHA</span>
						<span className="hv2-brand__tag">EUROPEAN PREMIUM FASHION</span>
					</div>
				</div>
				<button
					type="button"
					className="hv2-bell"
					onClick={() => setNotifyOpen(true)}
					aria-label="Уведомления"
				>
					<svg viewBox="0 0 24 24" className="hv2-bell__icon" aria-hidden>
						<path
							fill="none"
							stroke="currentColor"
							strokeWidth="1.3"
							d="M6.5 17.5h11M7.2 17.2V11a4.8 4.8 0 0 1 9.6 0v6.2M10 17.5a2 2 0 0 0 4 0"
						/>
					</svg>
					{!hasPush ? <span className="hv2-bell__dot" aria-hidden /> : null}
				</button>
			</header>

			<HeroBanner items={heroes} />

			<div className="hv2-below">
				<GenderCards />
				<BrandMarquee />
				<AccentBlocks
					onSelect={(accent) => {
						setLeadAccent(accent);
						setLeadOpen(true);
					}}
				/>
				<HomeBottomBar
					userInitial={userInitial}
					onUserClick={() => setUserOpen(true)}
					onAboutClick={() => navigate("/about")}
				/>
			</div>

			<UserMenu
				hideTrigger
				open={userOpen}
				onOpenChange={setUserOpen}
			/>
			<NotifySettingsModal open={notifyOpen} onClose={() => setNotifyOpen(false)} />
			<LeadRequestModal
				open={leadOpen}
				accent={leadAccent}
				onClose={() => {
					setLeadOpen(false);
					setLeadAccent(null);
				}}
			/>
		</div>
	);
}
