import { Link } from "react-router-dom";
import "./PrivacyConsent.css";

export default function PrivacyConsent({ className = "" }) {
	return (
		<p className={["privacy-consent", className].filter(Boolean).join(" ")}>
			Отправляя свои данные, вы соглашаетесь с{" "}
			<Link to="/privacy" className="privacy-consent__link">
				политикой конфиденциальности
			</Link>
			.
		</p>
	);
}
