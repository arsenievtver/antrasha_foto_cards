import {
	BrowserRouter as Router,
	Routes,
	Route,
	Navigate,
	useLocation,
} from "react-router-dom";
import { useEffect } from "react";
import UserMenu from "./components/UserMenu";
import SessionBootstrap from "./components/SessionBootstrap";
import { AuthProvider } from "./context/AuthContext";
import { VideoModalProvider } from "./context/VideoModalContext";
import Home from "./pages/Home";
import HomeV2 from "./pages/HomeV2";
import About from "./pages/About";
import Watch from "./pages/Watch";
import Swipe from "./pages/Swipe";
import ThankYou from "./pages/ThankYou";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import TryOnExperiment from "./pages/TryOnExperiment";
import "./App.css";
import {
	captureRefFromUrl,
	stripRefFromUrl,
} from "./utils/attribution.js";

captureRefFromUrl();
stripRefFromUrl();

function AppShell() {
	const { pathname } = useLocation();
	const scrollMain =
		pathname === "/thank-you" ||
		pathname === "/about" ||
		pathname === "/privacy" ||
		pathname === "/experiment/try-on" ||
		pathname.startsWith("/watch/");
	/* Главная (HomeV2) — свой низ с User; глобальный UserMenu не показываем */
	const showUserMenu =
		pathname === "/thank-you" ||
		pathname === "/about" ||
		pathname === "/privacy" ||
		pathname === "/classic";

	const isHomeV2 = pathname === "/";
	const immersiveTop = pathname === "/about" || isHomeV2;

	useEffect(() => {
		const root = document.documentElement;
		const theme = document.querySelector('meta[name="theme-color"]');
		const colorScheme = document.querySelector('meta[name="color-scheme"]');
		if (isHomeV2) {
			root.classList.add("hv2-edge");
			if (theme) theme.setAttribute("content", "#0c0b0a");
			if (colorScheme) colorScheme.setAttribute("content", "dark");
			root.style.colorScheme = "dark";
		} else {
			root.classList.remove("hv2-edge");
			if (theme) theme.setAttribute("content", "#2b2b2a");
			if (colorScheme) colorScheme.setAttribute("content", "dark");
			root.style.colorScheme = "";
		}
		return () => {
			root.classList.remove("hv2-edge");
			if (theme) theme.setAttribute("content", "#2b2b2a");
			if (colorScheme) colorScheme.setAttribute("content", "dark");
			root.style.colorScheme = "";
		};
	}, [isHomeV2]);

	return (
		<div
			className={`app-shell${immersiveTop ? " app-shell--immersive" : ""}${isHomeV2 ? " app-shell--hv2" : ""}`}
		>
			{showUserMenu ? <UserMenu /> : null}
			<div className={`app-main${scrollMain ? " app-main--scroll" : ""}`}>
				<Routes>
					<Route path="/" element={<HomeV2 />} />
					<Route path="/v2" element={<Navigate to="/" replace />} />
					<Route path="/classic" element={<Home />} />
					<Route path="/about" element={<About />} />
					<Route path="/watch/:slug" element={<Watch />} />
					<Route path="/swipe/:gender" element={<Swipe />} />
					<Route path="/thank-you" element={<ThankYou />} />
					<Route path="/privacy" element={<PrivacyPolicy />} />
					<Route path="/experiment/try-on" element={<TryOnExperiment />} />
				</Routes>
			</div>
		</div>
	);
}

export default function App() {
	return (
		<AuthProvider>
			<Router>
				<VideoModalProvider>
					<SessionBootstrap />
					<AppShell />
				</VideoModalProvider>
			</Router>
		</AuthProvider>
	);
}
