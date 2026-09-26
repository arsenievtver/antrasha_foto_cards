import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchActiveHeroBanners, fetchActivePromoBanner } from "../api/client.js";
import { wasPromoBannerSeenThisSession } from "../utils/promoBannerSession.js";
import { useAuth } from "../context/AuthContext";
import PromoBannerModal from "../components/PromoBannerModal.jsx";
import UserMenu from "../components/UserMenu";
import {
	isPushPermissionMissing,
	isPushSubscribedLocally,
} from "../push/notifications.js";
import AccentBlocks from "../components/home-v2/AccentBlocks";
import BrandMarquee from "../components/home-v2/BrandMarquee";
import GenderCards from "../components/home-v2/GenderCards";
import HeroBanner from "../components/home-v2/HeroBanner";
import HomeBottomBar from "../components/home-v2/HomeBottomBar";
import LeadRequestModal from "../components/home-v2/LeadRequestModal";
import PwaInstallPrompt from "../components/home-v2/PwaInstallPrompt";
import GiftMark from "../components/GiftMark";
import { HOME_V2_DEFAULT_HERO } from "../components/home-v2/homeV2Constants";
import logoMark from "../assets/image/logo-a-transparent.png";
import "./HomeV2.css";

export default function HomeV2() {
	const navigate = useNavigate();
	const { profile, isAuthenticated } = useAuth();
	const [heroes, setHeroes] = useState([HOME_V2_DEFAULT_HERO]);
	const [promoBanner, setPromoBanner] = useState(null);
	const [promoDismissed, setPromoDismissed] = useState(false);
	const [userOpen, setUserOpen] = useState(false);
	const [leadOpen, setLeadOpen] = useState(false);
	const [leadAccent, setLeadAccent] = useState(null);
	const [pushGranted, setPushGranted] = useState(() => !isPushPermissionMissing());

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
		let cancelled = false;
		(async () => {
			try {
				const data = await fetchActivePromoBanner();
				const banner = data.banner ?? null;
				if (!cancelled) {
					setPromoBanner(
						banner && !wasPromoBannerSeenThisSession(banner.id)
							? banner
							: null,
					);
				}
			} catch {
				/* сеть — главная без попапа */
			}
		})();
		return () => {
			cancelled = true;
		};
	}, []);

	useEffect(() => {
		setPushGranted(!isPushPermissionMissing());
	}, [userOpen, isAuthenticated]);

	const onPwaInstalled = useCallback(() => {
		if (!isPushSubscribedLocally() || isPushPermissionMissing()) setUserOpen(true);
	}, []);

	const userInitial =
		profile?.display_name?.trim()?.[0] ||
		profile?.phone?.replace(/\D/g, "")?.slice(-1) ||
		"";
	const hasGift = (profile?.gift_certificates || []).length > 0;

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
					className={
						userInitial ? "hv2-account" : "hv2-account hv2-account--guest"
					}
					onClick={() => setUserOpen(true)}
					aria-label={
						userInitial
							? hasGift
								? "Аккаунт, есть подарочный сертификат"
								: "Аккаунт"
							: "Войти"
					}
				>
					{userInitial ? (
						<span className="hv2-account__initial">{userInitial}</span>
					) : (
						"Войти"
					)}
					{userInitial && !pushGranted ? (
						<span className="hv2-account__dot" aria-hidden />
					) : null}
					{hasGift ? <GiftMark className="hv2-account__gift" /> : null}
				</button>
			</header>

			<HeroBanner items={heroes} />

			<div className="hv2-below">
				<BrandMarquee />
				<GenderCards />
				<AccentBlocks
					onSelect={(accent) => {
						setLeadAccent(accent);
						setLeadOpen(true);
					}}
				/>
				<HomeBottomBar onAboutClick={() => navigate("/about")} />
			</div>

			<PwaInstallPrompt onInstalled={onPwaInstalled} />

			{promoBanner && !promoDismissed ? (
				<PromoBannerModal
					banner={promoBanner}
					onClose={() => setPromoDismissed(true)}
				/>
			) : null}

			<UserMenu
				hideTrigger
				open={userOpen}
				onOpenChange={setUserOpen}
				onPushPermissionChange={setPushGranted}
			/>
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
