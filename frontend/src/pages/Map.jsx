import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useData } from "../api";
import { Feedback, Icon, PageHeading } from "../components";

export default function MapPage({ draft, onAdd }) {
  const { data, loading, error, reload } = useData("/destinations");
  const [selected, setSelected] = useState(null);
  const [tileError, setTileError] = useState(false);
  const container = useRef(null);
  const map = useRef(null);
  useEffect(() => {
    if (!data?.length || !container.current) return;
    const instance = L.map(container.current).setView([4.7, 10.8], 7);
    map.current = instance;
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(instance);
    tiles.on("tileerror", () => setTileError(true));
    const bounds = [];
    data.forEach((location) => {
      const point = [location.lat, location.lng];
      bounds.push(point);
      const label = document.createElement("span");
      label.textContent = location.name;
      L.circleMarker(point, { radius: 9, color: "#fff", weight: 3, fillColor: "#bd6338", fillOpacity: 1 })
        .addTo(instance).bindPopup(label).on("click", () => setSelected(location));
    });
    instance.fitBounds(bounds, { padding: [35, 35], maxZoom: 12 });
    return () => { instance.remove(); map.current = null; };
  }, [data]);
  useEffect(() => {
    if (selected && map.current) map.current.flyTo([selected.lat, selected.lng], 13);
  }, [selected]);
  return <section className="page"><PageHeading eyebrow="TAKE THE SCENIC ROUTE" title="A whole world, right here." /><p className="muted">Pick a place on the map or the list. Follow your curiosity from there.</p>
    <Feedback error={error} loading={loading} retry={reload} />
    {tileError && <Feedback error="Map tiles could not load. Check your internet connection. Destination coordinates and the list below remain available." />}
    <div className="map-layout"><div ref={container} className="geographic-map" role="region" aria-label="Interactive OpenStreetMap of Cameroon destinations" />
      <aside className="map-list">{data?.map((destination) => <button key={destination.id} className={selected?.id === destination.id ? "active" : ""} onClick={() => setSelected(destination)}><img src={destination.image} alt="" /><span><strong>{destination.name}</strong><small><Icon name="pin" size={12} />{destination.city}</small></span><Icon name="arrow" size={15} /></button>)}</aside></div>
    {selected && <div className="map-selection"><div><p className="eyebrow">YOUR NEXT STOP?</p><h2>{selected.name}</h2><p>{selected.description}</p><small className="muted">Approximate coordinates: {selected.lat}, {selected.lng}</small></div><button className="primary" disabled={draft.destination_ids.includes(selected.id)} onClick={() => onAdd(selected)}>{draft.destination_ids.includes(selected.id) ? "Added to your draft" : "Add to itinerary"}<Icon name="trip" size={18} /></button></div>}
    <p className="data-note">Map tiles require internet access and are provided by OpenStreetMap. Locations are approximate planning references, not navigation instructions.</p>
  </section>;
}
