import "./HomeBottomBar.css";

export default function HomeBottomBar({ onAboutClick }) {
	return (
		<div className="hv2-bottom">
			<button type="button" className="hv2-bottom__about" onClick={onAboutClick}>
				О бутике
			</button>
		</div>
	);
}
