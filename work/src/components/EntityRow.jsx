import { Link } from "react-router-dom";

export default function EntityRow({ to, title, subtitle, metric, metricSub, style }) {
  return (
    <Link to={to} className="entity-row">
      <div className="entity-row__body">
        <div className="entity-row__title">{title}</div>
        {subtitle ? <div className="entity-row__sub">{subtitle}</div> : null}
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
