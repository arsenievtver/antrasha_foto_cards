import { useNavigate } from "react-router-dom";
import { MaleShape, FemaleShape } from "../components/DiagonalCards";
import logo from "../assets/image/лого А на черном-cropped.svg";
import "./Home.css"
import menImage from "../assets/image/2m.jpeg";
import womenImage from "../assets/image/1w.jpeg";


export default function Home() {
  const navigate = useNavigate();

  return (
      <div className="page">
        <div className="page-home-body">
          <img src={logo} alt="Logo" className="logo" />
          <div className="home">
              <div className="shape-wrapper">
                  <MaleShape
                      className="shape male-color"
                      image={menImage}
                      onClick={() => navigate("/swipe/male")}
                  />
                  <span className="shape-label male-label">men collections</span>
              </div>

              <div className="shape-wrapper">
                  <FemaleShape
                      className="shape female-color"
                      image={womenImage}
                      onClick={() => navigate("/swipe/female")}
                  />
                  <span className="shape-label female-label">women collections</span>
              </div>
          </div>
          <div className="home-about-wrap">
            <button
              type="button"
              className="home-about-btn"
              onClick={() => navigate("/about")}
            >
              об ANTRASHA
            </button>
          </div>
        </div>
      </div>
  );
}