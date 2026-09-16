import { useEffect, useRef, useState } from "react";
import { Map as MapLibreMap, Marker, NavigationControl, ScaleControl, setWorkerUrl } from "maplibre-gl";
import mapWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import { request, useData } from "../api";
import { Feedback, Icon, PageHeading } from "../components";
import "./map.css";

const CAMEROON_BOUNDS = [[8.3, 1.6], [16.3, 13.2]];
const MAP_STYLE = import.meta.env.VITE_MAP_STYLE_URL || "https://tiles.openfreemap.org/styles/liberty";
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// MapLibre's default relative worker URL is not preserved by Vite's hashed bundles.
setWorkerUrl(mapWorkerUrl);

export default function MapPage({ draft, onAdd }) {
  const catalogue = useData("/destinations");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [selected, setSelected] = useState(null);
  const [mapError, setMapError] = useState("");
  const [mapReady, setMapReady] = useState(false);
  const [mapRendered, setMapRendered] = useState(false);
  const [mapVersion, setMapVersion] = useState(0);
  const [tilted, setTilted] = useState(true);
  const container = useRef(null);
  const map = useRef(null);
  const markers = useRef([]);
  const searchRequest = useRef(null);

  useEffect(() => {
    let instance;
    let stopped = false;
    let timer;
    let observer;
    const controller = new AbortController();
    setMapReady(false); setMapRendered(false); setMapError("");
    async function initialize() {
      // A failed module download otherwise leaves MapLibre's shared worker pool unusable on retry.
      try {
        const response = await fetch(mapWorkerUrl, {
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
        });
        if (!response.ok || !/\b(?:javascript|ecmascript)\b/i.test(response.headers.get("content-type") || "")) {
          throw new Error(`Invalid map worker response (${response.status})`);
        }
        await response.arrayBuffer();
      } catch (error) {
        if (!stopped) {
          console.error("Map worker download failed", error);
          setMapError("The map engine could not load. Check your connection and try again.");
        }
        return;
      }
      if (stopped) return;
      try {
        instance = new MapLibreMap({
          container: container.current, style: MAP_STYLE,
          bounds: CAMEROON_BOUNDS, maxBounds: CAMEROON_BOUNDS,
          fitBoundsOptions: { padding: 24, pitch: tilted ? 50 : 0, bearing: tilted ? -12 : 0 },
          maxPitch: 70, minZoom: 4, maxZoom: 18,
          attributionControl: { compact: true }, renderWorldCopies: false,
        });
      } catch {
        setMapError("This browser could not start the 3D map. Enable WebGL/hardware acceleration, or use the place lists and search below.");
        return;
      }
      map.current = instance;
      instance.addControl(new NavigationControl({ visualizePitch: true }), "top-right");
      instance.addControl(new ScaleControl(), "bottom-left");
      instance.on("error", () => {
        if (!stopped) setMapError("Some map data could not load. Check your connection or retry the map. Search and destination lists remain available.");
      });
      instance.on("style.load", () => {
        if (stopped) return;
        const style = instance.getStyle();
        if (style.sources.openmaptiles && !style.layers.some((layer) => layer.type === "fill-extrusion")) {
          const labelLayer = style.layers.find((layer) => layer.type === "symbol")?.id;
          instance.addLayer({
            id: "globetrotter-buildings", source: "openmaptiles", "source-layer": "building",
            type: "fill-extrusion", minzoom: 14,
            paint: {
              "fill-extrusion-color": "#b9c8b2",
              "fill-extrusion-height": ["coalesce", ["get", "render_height"], 3],
              "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
              "fill-extrusion-opacity": 0.85,
            },
          }, labelLayer);
        }
        setMapReady(true);
      });
      instance.on("load", () => {
        clearTimeout(timer);
        if (!stopped) { setMapRendered(true); setMapError(""); }
      });
      timer = setTimeout(() => {
        if (!stopped && !instance.loaded()) setMapError("Map details could not finish loading. Check your connection and try again. Search and destination lists remain available.");
      }, 15000);
      observer = new ResizeObserver(() => instance.resize());
      observer.observe(container.current);
    }
    initialize();
    return () => {
      stopped = true; controller.abort(); clearTimeout(timer); observer?.disconnect();
      markers.current.forEach((marker) => marker.remove()); markers.current = [];
      instance?.remove(); map.current = null;
    };
  }, [mapVersion]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !mapReady) return;
    markers.current.forEach((marker) => marker.remove());
    markers.current = [...(catalogue.data || []), ...(results || [])].map((place) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = `cameroon-marker ${place.source ? "search-marker" : ""}`;
      element.setAttribute("aria-label", `Show ${place.name} on map`);
      element.title = place.name;
      element.textContent = place.source ? "\u25C6" : "\u25CF";
      element.addEventListener("click", () => setSelected(place));
      return new Marker({ element }).setLngLat([place.lng, place.lat]).addTo(instance);
    });
    return () => { markers.current.forEach((marker) => marker.remove()); markers.current = []; };
  }, [catalogue.data, results, mapReady, mapVersion]);

  useEffect(() => {
    if (!map.current || !mapReady || !selected) return;
    map.current.flyTo({
      center: [selected.lng, selected.lat], zoom: selected.source ? 13 : 15.5,
      pitch: tilted ? 55 : 0, duration: reducedMotion() ? 0 : 900,
    });
  }, [selected, mapReady]);
  useEffect(() => () => searchRequest.current?.abort(), []);

  function toggleTilt() {
    const next = !tilted;
    setTilted(next);
    map.current?.easeTo({
      pitch: next ? 55 : 0, bearing: next ? -12 : 0, duration: reducedMotion() ? 0 : 500,
    });
  }
  async function search(event) {
    event.preventDefault();
    const value = query.trim();
    if (value.length < 3 || value.length > 120) { setSearchError("Enter a place name between 3 and 120 characters."); return; }
    searchRequest.current?.abort();
    const controller = new AbortController();
    searchRequest.current = controller;
    setSearching(true); setSearchError(""); setResults(null);
    try {
      const places = await request(`/map/search?q=${encodeURIComponent(value)}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setResults(places);
      if (places.length) setSelected(places[0]);
    } catch (err) {
      if (!controller.signal.aborted) setSearchError(err.message);
    } finally { if (!controller.signal.aborted) setSearching(false); }
  }
  function resetView() {
    setSelected(null);
    map.current?.fitBounds(CAMEROON_BOUNDS, {
      padding: 24, pitch: tilted ? 50 : 0, bearing: tilted ? -12 : 0, duration: reducedMotion() ? 0 : 700,
    });
  }
  return <section className="page cameroon-map-page">
    <PageHeading eyebrow="TAKE THE SCENIC ROUTE" title="Cameroon, from a new perspective." />
    <p className="muted">Pan and zoom within Cameroon. Search towns, landmarks, parks, and places beyond our collection.</p>
    <form className="cameroon-search" onSubmit={search}>
      <label htmlFor="cameroon-place-query"><span>Search anywhere in Cameroon</span><input id="cameroon-place-query" minLength={3} maxLength={120} required value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try Kribi, Limbe, or Mount Cameroon..." /></label>
      <button className="primary" disabled={searching}>{searching ? "Searching..." : "Search Cameroon"}<Icon name="search" size={17} /></button>
    </form>
    <p className="map-provider-note">Search by <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> / <a href="https://operations.osmfoundation.org/policies/nominatim/" target="_blank" rel="noreferrer">Nominatim</a>. Manual searches only, cached and limited to one request per second across this local app. Do not enter private or confidential addresses.</p>
    <Feedback error={searchError} loading={searching} />
    {results !== null && !searching && <section className="external-results" aria-label="Cameroon search results">
      <div className="section-title compact"><h2>{results.length ? `${results.length} places found` : "No matching places found"}</h2>
        <button className="text-button" type="button" onClick={() => { setResults(null); setSelected(null); }}>Clear results</button></div>
      {!results.length && <p className="muted">Try a nearby town or another spelling. Only places indexed in Cameroon are returned.</p>}
      <div>{results.map((place) => <button className={selected?.id === place.id ? "selected" : ""} key={place.id} onClick={() => setSelected(place)}><Icon name="pin" /><span><strong>{place.name}</strong><small>{place.display_name}</small></span></button>)}</div>
    </section>}
    <Feedback error={mapError} retry={() => setMapVersion((value) => value + 1)} />
    <div className="map-view-toolbar"><button className="secondary" type="button" disabled={!mapReady} aria-pressed={tilted} onClick={toggleTilt}>{tilted ? "Switch to 2D" : "Switch to 3D"}</button><button className="secondary" type="button" disabled={!mapReady} onClick={resetView}>Show Cameroon</button><small role="status">{mapError ? "Map incomplete. Use the lists or retry above." : mapRendered ? "Drag to move. Right-drag to tilt and rotate." : "Loading map details..."}</small></div>
    <div className="map-layout"><div className="geographic-map maplibre-container" ref={container} role="region" aria-label="3D map of Cameroon" />
      <aside className="map-list"><h3>From our collection</h3><Feedback loading={catalogue.loading} error={catalogue.error} retry={catalogue.reload} />{catalogue.data?.map((destination) => <div key={destination.id} className="map-place-row"><a href={`#/destination/${destination.id}`} aria-label={`View ${destination.name}`}><img src={destination.image} alt={destination.name} /></a><button className={selected?.id === destination.id ? "active" : ""} onClick={() => setSelected(destination)}><span><strong>{destination.name}</strong><small>{destination.city}</small></span><Icon name="pin" size={15} /></button></div>)}</aside></div>
    {selected && <div className="map-selection"><div><p className="eyebrow">{selected.source ? "FOUND IN CAMEROON" : "YOUR NEXT STOP?"}</p><h2>{selected.name}</h2><p>{selected.description || selected.display_name}</p><small className="muted">Coordinates: {selected.lat}, {selected.lng}</small></div>
      {!selected.source && <div className="form-stack"><a className="secondary" href={`#/destination/${selected.id}`}>View place and reviews</a><button className="primary" disabled={draft.destination_ids.includes(selected.id)} onClick={() => onAdd(selected)}>{draft.destination_ids.includes(selected.id) ? "Added to your draft" : "Add to itinerary"}</button></div>}
      {selected.source && <p className="external-place-note">This is an OpenStreetMap search result, not yet part of the curated itinerary catalogue.</p>}
    </div>}
    <p className="data-note">Map rendering by MapLibre; tiles and style by <a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a>, data &copy; OpenStreetMap contributors. Buildings appear in 3D when zoomed in where building data is available. This is not satellite imagery or live navigation. Maps require internet and WebGL; search/list results remain usable without WebGL.</p>
  </section>;
}
