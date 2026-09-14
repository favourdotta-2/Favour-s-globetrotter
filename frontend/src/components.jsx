export const preferences = ["culture", "food", "nature", "adventure", "history", "nightlife", "family"];

const shapes = {
  compass: <><circle cx="12" cy="12" r="9" /><path d="m16 8-3 5-5 3 3-5Z" /></>,
  trip: <><rect x="5" y="6" width="14" height="14" rx="3" /><path d="M9 6V3h6v3M9 10v6m6-6v6" /></>,
  map: <><path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Zm6-2v16m6-14v16" /></>,
  chat: <path d="M21 11a9 9 0 0 1-9 9H4l-2 2v-9a9 9 0 1 1 19-2Z" />,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 22v-3a8 8 0 0 1 16 0v3" /></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2" /></>,
  search: <><circle cx="10" cy="10" r="7" /><path d="m15 15 6 6" /></>,
};

export function Icon({ name = "compass", size = 21 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}

export function Feedback({ error, success, loading, retry }) {
  if (error) return <div className="feedback error" role="alert">{error}{retry && <button className="text-button" onClick={retry}>Try again</button>}</div>;
  if (loading) return <p className="feedback" role="status">Loading your next adventure...</p>;
  if (success) return <p className="feedback success" role="status">{success}</p>;
  return null;
}

export function Interests({ value, onChange }) {
  return <fieldset className="interests"><legend>Your travel interests</legend><div className="chips">{preferences.map((item) =>
    <button key={item} type="button" className={`chip ${value.includes(item) ? "selected" : ""}`} aria-pressed={value.includes(item)}
      onClick={() => onChange(value.includes(item) ? value.filter((current) => current !== item) : [...value, item])}>{item}</button>
  )}</div></fieldset>;
}

export function PageHeading({ eyebrow, title, children }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div>{children}</div>;
}

export function DestinationCard({ destination, onAdd, selected }) {
  return <article className="destination-card">
    <div className="card-photo"><img src={destination.image} alt={destination.name} loading="lazy" /><span>{destination.tags[0]}</span></div>
    <div className="card-body"><p className="location"><Icon name="pin" size={14} /> {destination.city}, Cameroon</p>
      <h3>{destination.name}</h3><p className="description">{destination.description}</p>
      <div className="card-bottom"><span><strong>${destination.avg_cost_per_day}</strong><small> / day, estimate</small></span>
        <button className={`round-button ${selected ? "selected" : ""}`} aria-label={`${selected ? "Added" : "Add"} ${destination.name} to itinerary`}
          disabled={selected} onClick={() => onAdd(destination)}>{selected ? "\u2713" : "+"}</button></div>
    </div>
  </article>;
}
