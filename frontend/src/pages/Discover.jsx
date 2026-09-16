import { useEffect, useState } from "react";
import { useData } from "../api";
import { DestinationCard, Feedback, Icon, PageHeading, preferences } from "../components";

export default function DiscoverPage({ user, draft, onAdd }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState("");
  const [maxCost, setMaxCost] = useState("");
  useEffect(() => { const timer = setTimeout(() => setQuery(search), 250); return () => clearTimeout(timer); }, [search]);
  const params = new URLSearchParams({ q: query, tag });
  if (maxCost !== "") params.set("max_cost", maxCost);
  const catalogue = useData(`/destinations?${params}`);
  const recommendations = useData("/recommendations?limit=3");
  const selected = (id) => draft.destination_ids.includes(id);
  return <section className="page discover-page">
    <PageHeading eyebrow={`A LITTLE WANDERLUST, ${user.username.toUpperCase()}?`} title="Where will curiosity take you?"><a className="secondary" href="#/itinerary">Plan a trip <Icon name="arrow" size={17} /></a></PageHeading>
    <div className="discover-hero"><div className="hero-copy"><p className="eyebrow">NOT FAR AWAY. A WORLD APART.</p><h2>Your next story<br />starts <em>in Cameroon.</em></h2><p>Chase a waterfall. Find a hidden corner.<br />Make room for a little extraordinary.</p><a className="cream-button" href="#destinations" onClick={(e) => { e.preventDefault(); document.getElementById("destinations").scrollIntoView({ behavior: "smooth" }); }}>Find my next adventure <Icon name="arrow" size={18} /></a></div><div className="hero-location"><Icon name="pin" /><div>Yaounde<small>The city of seven hills</small></div></div></div>
    <div className="section-title"><div><p className="eyebrow">FOLLOW YOUR CURIOSITY</p><h2>A place for every kind of traveler.</h2></div><span className="muted">Local places. Lasting memories.</span></div>
    <div className="filter-bar" id="destinations"><label className="search-label"><Icon name="search" /><span className="sr-only">Search destinations</span><input placeholder="A city, a place, a new experience..." value={search} onChange={(e) => setSearch(e.target.value)} /></label>
      <label className="budget-label">Daily budget<select value={maxCost} onChange={(e) => setMaxCost(e.target.value)}><option value="">Any budget</option><option value="35">Up to $35</option><option value="50">Up to $50</option><option value="75">Up to $75</option></select></label></div>
    <div className="category-tabs"><button className={!tag ? "active" : ""} onClick={() => setTag("")}>All experiences</button>{preferences.map((item) => <button key={item} className={tag === item ? "active" : ""} onClick={() => setTag(item)}>{item}</button>)}</div>
    <Feedback error={catalogue.error} loading={catalogue.loading} retry={catalogue.reload} />
    {!catalogue.loading && !catalogue.error && <><div className="results-label">{catalogue.data.length} places to spark your next story</div><div className="cards">{catalogue.data.map((destination) => <DestinationCard key={destination.id} destination={destination} onAdd={onAdd} selected={selected(destination.id)} />)}</div>
      {catalogue.data.length === 0 && <div className="empty-state"><Icon name="search" size={36} /><h3>No places found just yet.</h3><p>Try another search or clear your filters.</p><button className="secondary" onClick={() => { setSearch(""); setQuery(""); setTag(""); setMaxCost(""); }}>Clear filters</button></div>}</>}
    <div className="section-title"><div><p className="eyebrow">A LITTLE MORE YOU</p><h2>Picked for your kind of adventure.</h2></div><a className="text-button" href="#/profile">Refine your interests <Icon name="arrow" size={16} /></a></div>
    <Feedback loading={recommendations.loading} error={recommendations.error} retry={recommendations.reload} />
    {!recommendations.error && <div className="recommendation-grid">{recommendations.data?.map((destination) => <a className="recommendation" key={destination.id} href={`#/destination/${destination.id}`}>
      <img src={destination.image} alt="" /><div><small>{destination.city}</small><h3>{destination.name}</h3><span>Discover this place <Icon name="arrow" size={16} /></span></div></a>)}</div>}
    <p className="data-note">Planning inspiration, not live booking information. Budgets are illustrative USD/day and coordinates are approximate. Check local access and prices before traveling.</p>
  </section>;
}
