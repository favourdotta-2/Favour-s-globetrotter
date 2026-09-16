import { useEffect, useState } from "react";
import { request, useData } from "../api";
import { Avatar, Feedback, Icon, StarRating } from "../components";

export default function DestinationPage({ destinationId, user, draft, onAdd }) {
  const path = `/destinations/${encodeURIComponent(destinationId)}`;
  const place = useData(path);
  const ownReview = useData(`${path}/review`);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  useEffect(() => {
    if (!ownReview.loading && !ownReview.error) {
      setRating(ownReview.data?.rating || 0);
      setComment(ownReview.data?.comment || "");
    }
  }, [ownReview.data, ownReview.loading, ownReview.error]);

  async function save(event) {
    event.preventDefault();
    if (!rating || !comment.trim()) { setError("Choose a star rating and write a comment about this place."); return; }
    setPending(true); setError(""); setSuccess("");
    try {
      const saved = await request(`${path}/review`, { method: "PUT", body: { rating, comment } });
      ownReview.setData(saved); place.reload(); setSuccess("Your review is saved. Thanks for sharing your experience.");
    } catch (err) { setError(err.message); }
    finally { setPending(false); }
  }
  async function remove() {
    setPending(true); setError(""); setSuccess("");
    try {
      await request(`${path}/review`, { method: "DELETE" });
      ownReview.setData(null); place.reload(); setRating(0); setComment(""); setSuccess("Your review has been removed.");
    } catch (err) { setError(err.message); }
    finally { setPending(false); }
  }
  const destination = place.data;
  const reviewDisabled = pending || ownReview.loading || Boolean(ownReview.error);
  return <section className="page destination-page">
    <a className="text-button detail-back" href="#/discover">&larr; Back to discovery</a>
    <Feedback loading={place.loading && !destination} error={place.error} retry={place.reload} />
    {destination && !place.error && <>
      <div className="destination-hero"><img src={destination.image} alt={destination.name} />
        <div className="destination-hero-copy"><p className="eyebrow">A CLOSER LOOK AT CAMEROON</p><h1>{destination.name}</h1><p><Icon name="pin" size={17} /> {destination.city}, {destination.country}</p></div></div>
      <div className="destination-overview"><div><p className="eyebrow">MAKE ROOM FOR A LITTLE EXTRAORDINARY</p><h2>Get to know the place.</h2><p>{destination.description}</p>
        <div className="chips">{destination.tags.map((tag) => <span className="chip" key={tag}>{tag}</span>)}</div>
        <div className="destination-rating"><StarRating value={destination.rating_average || 0} /><strong>{destination.rating_average ?? "Not rated yet"}</strong><span>{destination.review_count} {destination.review_count === 1 ? "review" : "reviews"}</span></div>
      </div><aside className="destination-plan panel"><p className="eyebrow">YOUR NEXT STOP</p><p className="place-budget"><strong>${destination.avg_cost_per_day}</strong> / day</p><small>Illustrative planning budget, not a live price.</small>
        <button className="primary" disabled={draft.destination_ids.includes(destination.id)} onClick={() => onAdd(destination)}>{draft.destination_ids.includes(destination.id) ? "Added to your itinerary" : "Add to itinerary"}<Icon name="trip" size={17} /></button><a href="#/map" className="secondary">Explore the map <Icon name="map" size={17} /></a></aside></div>
      <div className="reviews-layout"><div><div className="section-title compact"><h2>Stories from fellow travelers</h2><span className="muted">{destination.review_count} reviews</span></div>
        {!destination.reviews.length && <div className="empty-state"><Icon name="chat" size={38} /><h3>Been here? Tell the story.</h3><p>Your review could inspire someone's next adventure.</p></div>}
        <div className="review-list">{destination.reviews.map((review) => {
          const author = review.username === user.username ? user : review.author;
          return <article className="review-card" key={review.id}><div className="review-heading"><Avatar user={author} /><div><strong>{author?.full_name || review.username}</strong><small>{new Date(review.updated_at).toLocaleDateString()}</small></div><StarRating value={review.rating} /></div><p className="preserve-text">{review.comment}</p></article>;
        })}</div>
        {destination.review_count > destination.reviews.length && <p className="data-note">Showing the latest {destination.reviews.length} reviews. The average includes all reviews.</p>}
      </div><form className="panel form-stack review-editor" onSubmit={save}><h2>{ownReview.data ? "Your experience, updated." : "Leave a little inspiration."}</h2><p className="muted">One review per traveler. You can edit your rating and comment at any time.</p>
        <Feedback error={ownReview.error} loading={ownReview.loading} retry={ownReview.reload} />
        <StarRating value={rating} onChange={setRating} label="Rate this place" disabled={reviewDisabled} />
        <label>Your comment<textarea required minLength={1} maxLength={2000} value={comment} disabled={reviewDisabled} onChange={(event) => setComment(event.target.value)} placeholder="What did you love? What should other travelers know?" /></label>
        <small className="muted">{comment.length}/2000 / Your review is visible to other travelers.</small>
        <Feedback error={error} success={success} /><button className="primary" disabled={reviewDisabled}>{pending ? "Saving..." : ownReview.data ? "Update my review" : "Post my review"}</button>
        {ownReview.data && <button type="button" className="danger-link" disabled={reviewDisabled} onClick={remove}>Delete my review</button>}
      </form></div>
    </>}
  </section>;
}
