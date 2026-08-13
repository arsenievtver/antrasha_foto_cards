import { useNavigate, useParams } from "react-router-dom";
import VideoModal from "../components/VideoModal";

export default function Watch() {
	const { slug } = useParams();
	const navigate = useNavigate();

	function onClose() {
		if (window.history.length > 1) navigate(-1);
		else navigate("/", { replace: true });
	}

	return (
		<div className="watch-page" style={{ minHeight: "100%", background: "#0c0b0a" }}>
			<VideoModal slug={slug} onClose={onClose} />
		</div>
	);
}
