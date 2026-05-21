import { useEffect } from "react";
import { ensureSessionId } from "../api/client.js";

/** Создаёт/привязывает сессию при любом заходе (не только на экране свайпа). */
export default function SessionBootstrap() {
	useEffect(() => {
		ensureSessionId().catch(() => {});
	}, []);
	return null;
}
