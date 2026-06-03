import {
	BrowserRouter as Router,
	Routes,
	Route,
	useLocation,
} from "react-router-dom";
import UserMenu from "./components/UserMenu";
import SessionBootstrap from "./components/SessionBootstrap";
import { AuthProvider } from "./context/AuthContext";
import Home from "./pages/Home";
import About from "./pages/About";
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
		pathname === "/experiment/try-on";
	const showUserMenu =
		pathname === "/" ||
		pathname === "/thank-you" ||
		pathname === "/about" ||
		pathname === "/privacy";

	const immersiveTop = pathname === "/about";

	return (
		<div className={`app-shell${immersiveTop ? " app-shell--immersive" : ""}`}>
			{showUserMenu ? <UserMenu /> : null}
			<div className={`app-main${scrollMain ? " app-main--scroll" : ""}`}>
				<Routes>
					<Route path="/" element={<Home />} />
					<Route path="/about" element={<About />} />
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
				<SessionBootstrap />
				<AppShell />
			</Router>
		</AuthProvider>
	);
}