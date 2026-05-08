import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useState,
} from "react";
import { fetchMe, getAuthToken, setAuthToken } from "../api/client";

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
				setAuthToken(null);
				setToken(null);
				setProfile(null);
				return null;
			}
			setProfile(me);
			return me;
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

	const logout = useCallback(() => {
		setAuthToken(null);
		setToken(null);
		setProfile(null);
	}, []);

	const loginWithToken = useCallback((accessToken) => {
		setAuthToken(accessToken);
		setToken(accessToken);
	}, []);

	const value = useMemo(
		() => ({
			token,
			profile,
			loading,
			isAuthenticated: !!profile,
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
