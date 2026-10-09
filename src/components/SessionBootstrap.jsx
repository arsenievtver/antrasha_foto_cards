import { useEffect } from "react";
import { ensureSessionId } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { claimWelcomeGiftIfReady } from "../push/notifications.js";

/** Создаёт/привязывает сессию при любом заходе (не только на экране свайпа). */
export default function SessionBootstrap() {
	const { token, refreshProfile } = useAuth();

	useEffect(() => {
		ensureSessionId().catch(() => {});
	}, []);

	useEffect(() => {
		if (!token) return undefined;
		let cancelled = false;
		claimWelcomeGiftIfReady()
			.then((issued) => {
				if (!cancelled && issued) return refreshProfile();
				return null;
			})
			.catch(() => {});
		return () => {
			cancelled = true;
		};
	}, [token, refreshProfile]);

	return null;
}
