import {
	BrowserRouter as Router,
	Routes,
	Route,
	useLocation,
} from "react-router-dom";
import UserMenu from "./components/UserMenu";
import { AuthProvider } from "./context/AuthContext";
import Home from "./pages/Home";
import Swipe from "./pages/Swipe";
import ThankYou from "./pages/ThankYou";
import "./App.css";

function AppShell() {
	const { pathname } = useLocation();
	const scrollMain = pathname === "/thank-you";

	return (
		<div className="app-shell">
			<UserMenu />
			<div className={`app-main${scrollMain ? " app-main--scroll" : ""}`}>
				<Routes>
					<Route path="/" element={<Home />} />
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