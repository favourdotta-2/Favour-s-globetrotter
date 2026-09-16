import { useState } from "react";
import { request, useData } from "../api";
import { Feedback, Icon, PageHeading } from "../components";

export const emptyDraft = () => ({ id: null, title: "", destination_ids: [], start_date: "", end_date: "", notes: "" });

export default function ItineraryPage({ draft, setDraft, navigate }) {
  const catalogue = useData("/destinations");
  const trips = useData("/itineraries");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(null);
  const byId = new Map(catalogue.data?.map((item) => [item.id, item]));
  const update = (field, value) => setDraft((current) => ({ ...current, [field]: value }));
  async function action(operation) {
    setPending(true); setError(""); setSuccess("");
    try { await operation(); }
    catch (err) { setError(err.message); }
    finally { setPending(false); }
  }
  async function submit(event) {
    event.preventDefault();
    if (!draft.destination_ids.length) { setError("Add at least one destination to your itinerary."); return; }
    if (Boolean(draft.start_date) !== Boolean(draft.end_date) || (draft.start_date && draft.end_date < draft.start_date)) {
      setError("Provide both dates in chronological order, or leave both empty."); return;
    }
    await action(async () => {
      await request(draft.id ? `/itineraries/${draft.id}` : "/itineraries", { method: draft.id ? "PUT" : "POST", body: {
        title: draft.title, destination_ids: draft.destination_ids,
        start_date: draft.start_date || null, end_date: draft.end_date || null, notes: draft.notes,
      } });
      setDraft((current) => current === draft ? emptyDraft() : current);
      setSuccess("Your itinerary is saved. Time to look forward to it.");
      trips.reload();
    });
  }
  function move(index, direction) {
    const ids = [...draft.destination_ids];
    [ids[index], ids[index + direction]] = [ids[index + direction], ids[index]];
    update("destination_ids", ids);
  }
  function edit(trip) {
    if (draft.title || draft.destination_ids.length) {
      setError("Save or clear your current draft before opening another itinerary."); return;
    }
    setDraft({ id: trip.id, title: trip.title, destination_ids: trip.destination_ids, start_date: trip.start_date || "", end_date: trip.end_date || "", notes: trip.notes });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  return <section className="page"><PageHeading eyebrow="TURN SOMEDAY INTO A PLAN" title="Your next chapter, mapped out."><button className="secondary" onClick={() => navigate("discover")}>Find more places <Icon name="arrow" size={17} /></button></PageHeading>
    <Feedback error={error} success={success} />
    <div className="itinerary-layout"><form className="panel form-stack trip-editor" onSubmit={submit}>
      <div className="section-title compact"><h2>{draft.id ? "Edit your itinerary" : "Build a little escape"}</h2><Icon name="trip" /></div>
      <fieldset disabled={pending}><label>Trip name<input required minLength={2} maxLength={100} placeholder="A weekend worth remembering" value={draft.title} onChange={(e) => update("title", e.target.value)} /></label>
        <div className="date-fields"><label>Start date<input type="date" value={draft.start_date} onChange={(e) => update("start_date", e.target.value)} /></label><label>End date<input type="date" min={draft.start_date || undefined} value={draft.end_date} onChange={(e) => update("end_date", e.target.value)} /></label></div><p className="muted small">Still dreaming? Leave both dates empty.</p>
        <h3>The stops along the way <span className="count">{draft.destination_ids.length}</span></h3>
        <Feedback error={catalogue.error} loading={catalogue.loading} retry={catalogue.reload} />
        {draft.destination_ids.length === 0 && <p className="empty-inline">Your journey is a blank canvas. Add a destination below or browse Discover.</p>}
        <ol className="draft-stops">{draft.destination_ids.map((id, index) => <li key={id}><span className="stop-number">{index + 1}</span><span>{byId.get(id)?.name || id}</span><div className="stop-controls">
          <button type="button" disabled={index === 0} aria-label={`Move ${byId.get(id)?.name || id} up`} onClick={() => move(index, -1)}>&uarr;</button>
          <button type="button" disabled={index === draft.destination_ids.length - 1} aria-label={`Move ${byId.get(id)?.name || id} down`} onClick={() => move(index, 1)}>&darr;</button>
          <button type="button" aria-label={`Remove ${byId.get(id)?.name || id}`} onClick={() => update("destination_ids", draft.destination_ids.filter((item) => item !== id))}>&times;</button></div></li>)}</ol>
        <label>Add a destination<select value="" onChange={(e) => { if (e.target.value) update("destination_ids", [...draft.destination_ids, e.target.value]); }}><option value="">Choose your next stop</option>{catalogue.data?.filter((item) => !draft.destination_ids.includes(item.id)).map((item) => <option key={item.id} value={item.id}>{item.name} - {item.city}</option>)}</select></label>
        <label>Notes for the journey<textarea maxLength={500} placeholder="Things to pack, people to meet, food to try..." value={draft.notes} onChange={(e) => update("notes", e.target.value)} /></label>
        <div className="button-row"><button className="primary" disabled={!draft.destination_ids.length}>{pending ? "Saving..." : "Save itinerary"}<Icon name="arrow" size={17} /></button><button className="text-button" type="button" onClick={() => setDraft(emptyDraft())}>Clear draft</button></div>
      </fieldset>
    </form><div><div className="section-title compact"><h2>Saved journeys</h2><span className="muted">{trips.data?.length || 0} itineraries</span></div>
      <Feedback error={trips.error} loading={trips.loading} retry={trips.reload} />
      {!trips.loading && !trips.error && trips.data?.length === 0 && <div className="empty-state"><Icon name="trip" size={42} /><h3>The best trips start here.</h3><p>Your saved itineraries will live in this space.<br />Make your first one a good one.</p></div>}
      <div className="saved-trips">{trips.data?.map((trip) => <article className="saved-trip" key={trip.id}>
        <a href={`#/destination/${trip.destinations[0]?.id}`} aria-label={`View ${trip.destinations[0]?.name}`}><img className="trip-cover" src={trip.destinations[0]?.image} alt={trip.destinations[0]?.name} /></a><div className="trip-body"><p className="eyebrow">{trip.destinations.length} STOPS / YOUR JOURNEY</p><h3>{trip.title}</h3><p className="muted">{trip.start_date ? `${trip.start_date} to ${trip.end_date}` : "Dates to be discovered"}</p>
          <div className="chips">{trip.destinations.map((item, index) => <span className="tag" key={item.id}>{index + 1}. {item.name}</span>)}</div><p className="preserve-text">{trip.notes}</p>
          <div className="button-row"><button className="secondary" disabled={pending} onClick={() => edit(trip)}>Edit trip</button>
            {!trip.share_id && <button className="text-button" disabled={pending} onClick={() => action(async () => { await request(`/itineraries/${trip.id}/share`, { method: "POST" }); trips.reload(); setSuccess("Sharing enabled. Anyone with the link can see this trip and its notes."); })}>Enable sharing</button>}
            <button className="danger-link" disabled={pending} onClick={() => setConfirmDelete(trip.id)}>Delete</button>
          </div>
          {trip.share_id && <div className="share-box"><label>Anyone with this link can view your trip<input readOnly value={`${window.location.origin}${window.location.pathname}#/shared/${trip.share_id}`} onFocus={(e) => e.target.select()} /></label><div className="button-row"><a className="text-button" href={`#/shared/${trip.share_id}`} target="_blank" rel="noreferrer">View shared trip</a><button className="text-button" disabled={pending} onClick={() => action(async () => { await navigator.clipboard.writeText(`${window.location.origin}${window.location.pathname}#/shared/${trip.share_id}`); setSuccess("Share link copied."); })}>Copy link</button><button className="danger-link" disabled={pending} onClick={() => action(async () => { await request(`/itineraries/${trip.id}/share`, { method: "DELETE" }); trips.reload(); setSuccess("Sharing disabled. The old link no longer works."); })}>Revoke link</button></div></div>}
          {confirmDelete === trip.id && <div className="feedback error"><p>Delete this itinerary permanently?</p><div className="button-row"><button className="secondary" disabled={pending} onClick={() => action(async () => { await request(`/itineraries/${trip.id}`, { method: "DELETE" }); if (draft.id === trip.id) setDraft(emptyDraft()); setConfirmDelete(null); trips.reload(); setSuccess("Itinerary deleted."); })}>Confirm delete</button><button className="text-button" onClick={() => setConfirmDelete(null)}>Keep it</button></div></div>}
        </div></article>)}</div>
    </div></div>
  </section>;
}
