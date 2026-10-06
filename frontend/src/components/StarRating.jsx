/** Read-only stars when onChange is absent; a 1-5 picker otherwise. */
export default function StarRating({ value = 0, onChange, size = "md" }) {
  if (!onChange) {
    return (
      <span className={`stars stars-${size}`} aria-label={`Rated ${value.toFixed(1)} out of 5`}>
        <span aria-hidden="true">★</span> {value > 0 ? value.toFixed(1) : "New"}
      </span>
    );
  }
  return (
    <div className="star-picker" role="radiogroup" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          className={`star-btn${n <= value ? " on" : ""}`} onClick={() => onChange(n)}>
          ★
        </button>
      ))}
    </div>
  );
}
