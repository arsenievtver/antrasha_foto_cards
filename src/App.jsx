import {
	BrowserRouter as Router,
	Routes,
	Route,
	useLocation,
} from "react-router-dom";
import UserMenu from "./components/UserMenu";
import { AuthProvider } from "./context/AuthContext";
import Home from "./pages/Home";
import About from "./pages/About";
import Swipe from "./pages/Swipe";
import ThankYou from "./pages/ThankYou";
import "./App.css";

function AppShell() {
	const { pathname } = useLocation();
	const scrollMain = pathname === "/thank-you" || pathname === "/about";
	const showUserMenu =
		pathname === "/" || pathname === "/thank-you" || pathname === "/about";

	return (
		<div className="app-shell">
			{showUserMenu ? <UserMenu /> : null}
			<div className={`app-main${scrollMain ? " app-main--scroll" : ""}`}>
				<Routes>
					<Route path="/" element={<Home />} />
					<Route path="/about" element={<About />} />
					<Route path="/swipe/:gender" element={<Swipe />} />
					<Route path="/thank-you" element={<ThankYou />} />
				</Routes>
			</div>
		</div>
	);
}

export default function App() {
	return (
		<AuthProvider>
			<Router>
				<AppShell />
			</Router>
		</AuthProvider>
	);
}