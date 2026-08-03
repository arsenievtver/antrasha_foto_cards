import { Link } from "react-router-dom";
import {
  hasAiAssistantAccess,
  hasOutletAccess,
  hasOutletTransferAccess,
} from "../api.js";

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
        {hasOutletTransferAccess() ? (
          <Link to="/outlet-transfer" className="menu-list__item">
            <span className="menu-list__title">Аутлет: перенос</span>
            <span className="menu-list__hint">Очередь отфотканных → перенос в аутлет</span>
          </Link>
        ) : null}
        {hasAiAssistantAccess() ? (
          <Link to="/ai-assistant" className="menu-list__item">
            <span className="menu-list__title">AI помощник</span>
            <span className="menu-list__hint">Чат и табы по остаткам и продажам</span>
          </Link>
        ) : null}
      </nav>
    </div>
  );
}
