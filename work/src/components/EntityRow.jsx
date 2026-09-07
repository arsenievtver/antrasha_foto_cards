import { Link } from "react-router-dom";

export default function EntityRow({ to, title, subtitle, metric, metricSub, style, badges }) {
  return (
    <Link to={to} className="entity-row">
      <div className="entity-row__body">
        <div className="entity-row__title">{title}</div>
        {subtitle ? <div className="entity-row__sub">{subtitle}</div> : null}
        {badges?.length ? (
          <div className="entity-row__badges">
            {badges.map((b) => (
              <span key={b.label} className={`pp-badge pp-badge--${b.tone || "muted"}`}>
                {b.label}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="entity-row__right">
        <div className="entity-row__metric" style={style}>
          {metric}
        </div>
        {metricSub ? <div className="entity-row__metric-sub">{metricSub}</div> : null}
      </div>
    </Link>
  );
}
