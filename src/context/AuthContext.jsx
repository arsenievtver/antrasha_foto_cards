import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useState,
} from "react";
import {
	clearAuthTokens,
	fetchMe,
	getAuthToken,
	refreshAccessToken,
	setAuthToken,
} from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
	const [token, setToken] = useState(() => getAuthToken());
	const [profile, setProfile] = useState(null);
	const [loading, setLoading] = useState(() => !!getAuthToken());

	const refreshProfile = useCallback(async () => {
		const t = getAuthToken();
		if (!t) {
			setProfile(null);
			setLoading(false);
			return null;
		}
		setLoading(true);
		try {
			const me = await fetchMe();
			if (!me && getAuthToken()) {
				const renewed = await refreshAccessToken();
				if (renewed) {
					const retry = await fetchMe({ retryOn401: false });
					if (retry) {
						setProfile(retry);
						setToken(getAuthToken());
						return retry;
					}
				}
				clearAuthTokens();
				setToken(null);
				setProfile(null);
				return null;
			}
			setProfile(me);
			return me;
		} catch {
			// Сеть/5xx: не сбрасываем токен — profile не трогаем.
			return null;
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		if (!token) {
			setProfile(null);
			setLoading(false);
			return;
		}
		refreshProfile();
	}, [token, refreshProfile]);

	useEffect(() => {
		function onVisible() {
			if (document.visibilityState === "visible" && getAuthToken()) {
				refreshProfile();
			}
		}
		document.addEventListener("visibilitychange", onVisible);
		return () => document.removeEventListener("visibilitychange", onVisible);
	}, [refreshProfile]);

	const logout = useCallback(() => {
		clearAuthTokens();
		setToken(null);
		setProfile(null);
	}, []);

	const loginWithToken = useCallback((accessToken, refreshToken = null) => {
		setAuthToken(accessToken, refreshToken);
		setToken(accessToken);
	}, []);

	const value = useMemo(
		() => ({
			token,
			profile,
			loading,
			isAuthenticated: !!profile || !!token,
			logout,
			loginWithToken,
			refreshProfile,
		}),
		[token, profile, loading, logout, loginWithToken, refreshProfile],
	);

	return (
		<AuthContext.Provider value={value}>{children}</AuthContext.Provider>
	);
}

export function useAuth() {
	const ctx = useContext(AuthContext);
	if (!ctx) throw new Error("useAuth must be used within AuthProvider");
	return ctx;
}
