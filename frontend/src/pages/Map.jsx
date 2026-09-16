import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { request, useData } from "../api";
import { Feedback, Icon, PageHeading } from "../components";
import "./map.css";

const CAMEROON_BOUNDS = L.latLngBounds([[1.6, 8.3], [13.2, 16.3]]);
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function locate() {
  if (!window.isSecureContext) return Promise.reject(new Error("Location access requires HTTPS or localhost."));
  if (!navigator.geolocation) return Promise.reject(new Error("This browser does not support location access."));
  return new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, (error) => {
    const messages = {
      1: "Location permission was denied. Allow location access in your browser settings, then try again.",
      2: "Your location is unavailable. Enable your device's location services, then try again.",
      3: "Finding your location timed out. Move to a better signal and try again.",
    };
    reject(new Error(messages[error.code] || "Your location could not be determined. Please try again."));
  }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }));
}

function travelTime(seconds) {
  const minutes = Math.max(1, Math.round(seconds / 60));
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} hr ${minutes % 60} min`;
}

export default function MapPage({ draft, onAdd }) {
  const catalogue = useData("/destinations");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [selected, setSelected] = useState(null);
  const [mapError, setMapError] = useState("");
  const [mapReady, setMapReady] = useState(false);
  const [tilesReady, setTilesReady] = useState(false);
  const [mapVersion, setMapVersion] = useState(0);
  const [locationAllowed, setLocationAllowed] = useState(false);
  const [origin, setOrigin] = useState(null);
  const [route, setRoute] = useState(null);
  const [routeStatus, setRouteStatus] = useState("");
  const [routeError, setRouteError] = useState("");
  const [routeAttempt, setRouteAttempt] = useState(0);
  const container = useRef(null);
  const map = useRef(null);
  const searchRequest = useRef(null);

  const choosePlace = useCallback((place) => {
    searchRequest.current?.abort();
    setSearching(false);
    setSearchError("");
    setSelected({ ...place });
  }, []);

  useEffect(() => {
    let instance;
    let timer;
    let failedTiles = false;
    setMapReady(false); setTilesReady(false); setMapError("");
    try {
      instance = L.map(container.current, {
        maxBounds: CAMEROON_BOUNDS, maxBoundsViscosity: 1, maxZoom: 19, zoomSnap: 0.25,
      }).fitBounds(CAMEROON_BOUNDS, { padding: [24, 24] });
    } catch (error) {
      console.error("Map initialization failed", error);
      setMapError("The map could not start. Try again, or use the destination lists below.");
      instance?.remove();
      return;
    }
    map.current = instance;
    const resize = () => {
      instance.invalidateSize({ pan: false });
      instance.setMinZoom(instance.getBoundsZoom(CAMEROON_BOUNDS, false, [24, 24]));
    };
    resize();
    L.control.scale({ imperial: false }).addTo(instance);
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, bounds: CAMEROON_BOUNDS, noWrap: true,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    });
    tiles.on("loading", () => {
      failedTiles = false; setTilesReady(false); clearTimeout(timer);
      timer = setTimeout(() => setMapError("Map tiles could not finish loading. Check your connection and try again."), 15000);
    });
    tiles.on("tileerror", () => {
      failedTiles = true;
      setMapError("Some map tiles could not load. Check your connection and try again. Search and destination lists remain available.");
    });
    tiles.on("load", () => {
      clearTimeout(timer); setTilesReady(!failedTiles);
      if (!failedTiles) setMapError("");
    });
    tiles.addTo(instance);
    setMapReady(true);
    const observer = new ResizeObserver(resize);
    observer.observe(container.current);
    return () => {
      clearTimeout(timer); observer.disconnect(); tiles.off();
      instance.remove(); map.current = null;
    };
  }, [mapVersion]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const layer = L.layerGroup().addTo(instance);
    [...(catalogue.data || []), ...(results || [])].forEach((place) => {
      const marker = L.marker([place.lat, place.lng], {
        title: `Get driving route to ${place.name}`,
        icon: L.divIcon({
          className: `cameroon-marker ${place.source ? "search-marker" : ""}`,
          html: '<span aria-hidden="true">&#9679;</span>', iconSize: [28, 28], iconAnchor: [14, 14],
        }),
      }).addTo(layer).on("click", () => choosePlace(place));
      marker.getElement().setAttribute("aria-label", `Get driving route to ${place.name}`);
      const label = document.createElement("span");
      label.textContent = place.name;
      marker.bindTooltip(label);
    });
    return () => layer.remove();
  }, [catalogue.data, results, mapVersion, choosePlace]);

  useEffect(() => {
    if (selected && map.current) {
      map.current.flyTo([selected.lat, selected.lng], 13, { animate: !reducedMotion() });
    }
  }, [selected, mapVersion]);

  useEffect(() => {
    const controller = new AbortController();
    setRoute(null); setOrigin(null); setRouteError(""); setRouteStatus("");
    if (!selected || !locationAllowed) return;
    async function directions() {
      setRouteStatus("locating");
      try {
        const position = await locate();
        // Geolocation callbacks cannot be cancelled; ignore results from an older selection.
        if (controller.signal.aborted) return;
        const { latitude: lat, longitude: lng, accuracy } = position.coords;
        if (!Number.isFinite(lat) || !Number.isFinite(lng) || !CAMEROON_BOUNDS.contains([lat, lng])) {
          throw new Error("Your detected location is outside Cameroon. Driving directions are currently available only from locations within Cameroon.");
        }
        setOrigin({ lat, lng, accuracy });
        setRouteStatus("routing");
        const nextRoute = await request("/map/route", {
          method: "POST", signal: controller.signal,
          body: { origin: { lat, lng }, destination: { lat: selected.lat, lng: selected.lng } },
        });
        if (!controller.signal.aborted) setRoute(nextRoute);
      } catch (error) {
        if (!controller.signal.aborted) setRouteError(error.message);
      } finally {
        if (!controller.signal.aborted) setRouteStatus("");
      }
    }
    directions();
    return () => controller.abort();
  }, [selected, locationAllowed, routeAttempt]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !origin) return;
    const layer = L.layerGroup().addTo(instance);
    const start = [origin.lat, origin.lng];
    L.circleMarker(start, {
      radius: 8, color: "#fff", weight: 3, fillColor: "#2875ce", fillOpacity: 1,
      className: "user-location-marker",
    }).addTo(layer).bindTooltip("Your location");
    if (Number.isFinite(origin.accuracy) && origin.accuracy > 0) {
      L.circle(start, { radius: origin.accuracy, color: "#2875ce", weight: 1, fillOpacity: 0.08, interactive: false }).addTo(layer);
    }
    if (route) {
      const line = L.geoJSON(route.geometry, {
        style: { color: "#2875ce", weight: 6, opacity: 0.9, className: "driving-route" },
        interactive: false,
      }).addTo(layer);
      const bounds = line.getBounds().extend(start).extend([selected.lat, selected.lng]);
      instance.fitBounds(bounds, { padding: [35, 35], maxZoom: 15, animate: !reducedMotion() });
    }
    return () => layer.remove();
  }, [origin, route, mapVersion]);

  useEffect(() => () => searchRequest.current?.abort(), []);

  async function search(event) {
    event.preventDefault();
    const value = query.trim();
    if (value.length < 3 || value.length > 120) { setSearchError("Enter a place name between 3 and 120 characters."); return; }
    searchRequest.current?.abort();
    const controller = new AbortController();
    searchRequest.current = controller;
    setSearching(true); setSearchError(""); setResults(null); setSelected(null);
    try {
      const places = await request(`/map/search?q=${encodeURIComponent(value)}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setResults(places);
      if (places.length) setSelected({ ...places[0] });
    } catch (error) {
      if (!controller.signal.aborted) setSearchError(error.message);
    } finally {
      if (!controller.signal.aborted) setSearching(false);
    }
  }
  function resetView() {
    searchRequest.current?.abort(); setSearching(false); setSelected(null);
    map.current?.fitBounds(CAMEROON_BOUNDS, { padding: [24, 24], animate: !reducedMotion() });
  }

  return <section className="page cameroon-map-page">
    <PageHeading eyebrow="TAKE THE SCENIC ROUTE" title="Your next stop, on the map." />
    <p className="muted">Explore Cameroon in 2D. Pick a destination or search for a place to see the driving route from your location.</p>
    <form className="cameroon-search" onSubmit={search}>
      <label htmlFor="cameroon-place-query"><span>Search anywhere in Cameroon</span><input id="cameroon-place-query" minLength={3} maxLength={120} required value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try Kribi, Limbe, or Mount Cameroon..." /></label>
      <button className="primary" disabled={searching}>{searching ? "Searching..." : "Search Cameroon"}<Icon name="search" size={17} /></button>
    </form>
    <p className="map-provider-note">Press Enter or Search Cameroon to select the first matching place and request directions. Search by <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> / <a href="https://operations.osmfoundation.org/policies/nominatim/" target="_blank" rel="noreferrer">Nominatim</a>. No autocomplete. Do not enter private or confidential addresses.</p>
    <Feedback error={searchError} loading={searching} />
    {results !== null && !searching && <section className="external-results" aria-label="Cameroon search results">
      <div className="section-title compact"><h2>{results.length ? `${results.length} places found` : "No matching places found"}</h2>
        <button className="text-button" type="button" onClick={() => { setResults(null); setSelected(null); }}>Clear results</button></div>
      {!results.length && <p className="muted">Try a nearby town or another spelling. Only places indexed in Cameroon are returned.</p>}
      <div>{results.map((place) => <button className={selected?.id === place.id ? "selected" : ""} key={place.id} onClick={() => choosePlace(place)}><Icon name="pin" /><span><strong>{place.name}</strong><small>{place.display_name}</small></span></button>)}</div>
    </section>}
    <section className="map-location-notice" aria-label="Location sharing for directions">
      <div><strong>Driving directions from your location</strong>
        <p>With your permission, your current and destination coordinates are sent to the public OSRM service to calculate a road route. GlobeTrotter does not save your location or route. Sharing is enabled only for this map visit.</p>
        {!selected && <small>First, select a destination on the map or in the list.</small>}
      </div>
      {!locationAllowed && selected && <button className="primary" onClick={() => setLocationAllowed(true)}>Use my location</button>}
      {locationAllowed && <button className="secondary" onClick={() => setLocationAllowed(false)}>Stop using my location</button>}
    </section>
    {selected && <section className="map-directions" aria-label="Driving directions">
      <div className="section-title compact"><h2>Directions to {selected.name}</h2>
        {locationAllowed && <button className="text-button" disabled={Boolean(routeStatus)} onClick={() => setRouteAttempt((value) => value + 1)}>Update route</button>}
      </div>
      {!locationAllowed && <p className="muted">Choose Use my location above, then allow location access in your browser to draw the route.</p>}
      {routeStatus && <p role="status">{routeStatus === "locating" ? "Finding your current location..." : "Finding a driving route..."}</p>}
      <Feedback error={routeError} retry={() => setRouteAttempt((value) => value + 1)} />
      {route && <div className="route-summary" role="status"><span><strong>{(route.distance_m / 1000).toFixed(1)} km</strong> by road</span><span><strong>{travelTime(route.duration_s)}</strong> estimated driving time</span></div>}
      {origin && <p className="map-provider-note">The blue marker is your detected location{Number.isFinite(origin.accuracy) ? ` (accuracy about ${Math.round(origin.accuracy)} m)` : ""}. The route connects the nearest mapped roads, not necessarily the exact door or entrance.</p>}
    </section>}
    <Feedback error={mapError} retry={() => setMapVersion((value) => value + 1)} />
    <div className="map-view-toolbar"><button className="secondary" type="button" disabled={!mapReady} onClick={resetView}>Show Cameroon</button><small role="status">{mapError ? "Map incomplete. Use the lists or retry above." : tilesReady ? "2D OpenStreetMap. Drag to move and use + or - to zoom." : "Loading map tiles..."}</small></div>
    <div className="map-layout"><div className="geographic-map" ref={container} role="region" aria-label="2D OpenStreetMap of Cameroon" />
      <aside className="map-list"><h3>From our collection</h3><Feedback loading={catalogue.loading} error={catalogue.error} retry={catalogue.reload} />{catalogue.data?.map((destination) => <div key={destination.id} className="map-place-row"><button aria-label={`Get driving route to ${destination.name}`} className={selected?.id === destination.id ? "active" : ""} onClick={() => choosePlace(destination)}><img src={destination.image} alt="" /><span><strong>{destination.name}</strong><small>{destination.city}</small></span><Icon name="pin" size={15} /></button></div>)}</aside></div>
    {selected && <div className="map-selection"><div><p className="eyebrow">{selected.source ? "FOUND IN CAMEROON" : "YOUR NEXT STOP?"}</p><h2>{selected.name}</h2><p>{selected.description || selected.display_name}</p><small className="muted">Coordinates: {selected.lat}, {selected.lng}</small></div>
      {!selected.source && <div className="form-stack"><a className="secondary" href={`#/destination/${selected.id}`}>View place and reviews</a><button className="primary" disabled={draft.destination_ids.includes(selected.id)} onClick={() => onAdd(selected)}>{draft.destination_ids.includes(selected.id) ? "Added to your draft" : "Add to itinerary"}</button></div>}
      {selected.source && <p className="external-place-note">This is an OpenStreetMap search result, not yet part of the curated itinerary catalogue.</p>}
    </div>}
    <p className="data-note">2D map by <a href="https://leafletjs.com/" target="_blank" rel="noreferrer">Leaflet</a>, tiles and data &copy; OpenStreetMap contributors. Driving routes by <a href="https://project-osrm.org/" target="_blank" rel="noreferrer">OSRM</a>. Internet and location permission are required for directions; location access needs HTTPS or localhost. Estimates do not include live traffic and are not turn-by-turn navigation. The public routing service is for this small demo, not production.</p>
  </section>;
}
