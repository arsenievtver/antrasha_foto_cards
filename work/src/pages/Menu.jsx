import { Link } from "react-router-dom";
import { hasOutletAccess } from "../api.js";

export default function Menu() {
  return (
    <div className="menu-page">
      <nav className="menu-list" aria-label="Дополнительно">
        <Link to="/for-order" className="menu-list__item">
          <span className="menu-list__title">Для заказа</span>
          <span className="menu-list__hint">Подсказки по сезону и брендам</span>
        </Link>
        {hasOutletAccess() ? (
          <Link to="/outlet" className="menu-list__item">
            <span className="menu-list__title">Аутлет: фото</span>
            <span className="menu-list__hint">Штрихкод → Fashn → МойСклад</span>
          </Link>
        ) : null}
      </nav>
    </div>
  );
}
