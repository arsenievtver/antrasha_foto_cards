export default function Switch({ checked, onChange, label }) {
  return (
    <div className="switch-row">
      <span>{label}</span>
      <button
        type="button"
        className="switch-toggle"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
      >
        <span className="switch-thumb" />
      </button>
    </div>
  );
}
