import { useEffect, useRef, useState } from "react";
import { IMAGE_TYPES, request, useData, validateFile } from "../api";
import { Avatar, Feedback, Icon, Interests, PageHeading, StarRating } from "../components";

export function AuthPage({ mode, navigate, onSuccess, notice }) {
  const [form, setForm] = useState({ username: "", password: "", full_name: "", preferences: ["culture", "nature"] });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const signup = mode === "signup";
  async function submit(event) {
    event.preventDefault();
    setPending(true); setError("");
    try { onSuccess(await request(signup ? "/auth/signup" : "/auth/login", { method: "POST", body: form })); }
    catch (err) { setError(err.message); }
    finally { setPending(false); }
  }
  return <main className="auth-shell">
    <section className="auth-visual"><img src="/auth/Yaounde_0.jpg" alt="Reunification Monument in Yaounde" />
      <a className="brand" href="#/login"><Icon />globetrotter.</a>
      <div className="auth-story"><p className="eyebrow">YOUR NEXT CHAPTER STARTS HERE</p><h1>Less ordinary.<br /><em>More adventure.</em></h1><p>From the rhythm of Yaounde to the quiet of the waterfalls. Find your Cameroon.</p><span><Icon name="pin" size={17} /> Yaounde, Cameroon</span></div>
    </section>
    <section className="auth-form-area"><div className="auth-top">New memories. Your kind of journey.</div>
      <form onSubmit={submit} className="auth-form"><p className="eyebrow">{signup ? "JOIN THE JOURNEY" : "YOUR ADVENTURE AWAITS"}</p>
        <h2>{signup ? "A world to discover." : "Good to see you again."}</h2><p className="muted">{signup ? "Create your traveler profile and start exploring." : "Log in to pick up where your curiosity left off."}</p>
        {notice && <Feedback success={notice} />}
        {signup && <label>Full name<input maxLength={80} autoComplete="name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="What should we call you?" /></label>}
        <label>Username<input required minLength={3} maxLength={40} pattern="[A-Za-z0-9_.\-]+" autoComplete="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="Your traveler name" /></label>
        <label>Password<input required type="password" minLength={signup ? 8 : 1} maxLength={128} autoComplete={signup ? "new-password" : "current-password"} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder={signup ? "At least 8 characters" : "Enter your password"} /></label>
        {signup && <Interests value={form.preferences} onChange={(preferences) => setForm({ ...form, preferences })} />}
        <Feedback error={error} /><button className="primary" disabled={pending}>{pending ? "Just a moment..." : signup ? "Create my account" : "Let's explore"}<Icon name="arrow" size={18} /></button>
        <p className="auth-switch">{signup ? "Already part of the journey?" : "First time here?"} <button type="button" className="text-button" onClick={() => { setError(""); navigate(signup ? "login" : "signup"); }}>{signup ? "Log in" : "Create an account"}</button></p>
        <small className="muted">A CS4122 travel assistant. No bookings or payments.</small>
      </form>
    </section>
  </main>;
}

function AppRatingPanel() {
  const saved = useData("/profile/app-rating");
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const panel = useRef(null);
  useEffect(() => {
    panel.current.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);
  useEffect(() => {
    if (saved.data) { setRating(saved.data.rating); setComment(saved.data.comment); }
  }, [saved.data]);
  async function submit(event) {
    event.preventDefault();
    if (!rating) { setError("Choose 1 to 5 stars before submitting."); return; }
    setPending(true); setError(""); setSuccess("");
    try {
      await request("/profile/app-rating", { method: "PUT", body: { rating, comment } });
      setSuccess("Thank you! Your GlobeTrotter rating has been saved.");
    } catch (err) { setError(err.message); }
    finally { setPending(false); }
  }
  return <form ref={panel} className="panel form-stack app-rating-panel" onSubmit={submit}><p className="eyebrow">HELP US MAKE THE JOURNEY BETTER</p><h2>Rate GlobeTrotter</h2><p className="muted">How is your experience with the app? This is app feedback, not a destination review.</p>
    <Feedback loading={saved.loading} error={saved.error} retry={saved.reload} /><StarRating label="Your app rating" value={rating} onChange={setRating} disabled={pending || saved.loading || Boolean(saved.error)} />
    <label>Suggestions (optional)<textarea maxLength={1000} value={comment} disabled={pending || saved.loading || Boolean(saved.error)} onChange={(event) => setComment(event.target.value)} placeholder="Tell us what made your journey easier, or what we could improve." /></label>
    <Feedback error={error} success={success} /><button className="primary" disabled={pending || saved.loading || Boolean(saved.error)}>{pending ? "Sending..." : "Save app rating"}</button>
  </form>;
}

export function ProfilePage({ user, setUser, onLogout }) {
  const [form, setForm] = useState({ full_name: user.full_name, preferences: user.preferences, bio: user.bio, home_city: user.home_city });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [avatarPending, setAvatarPending] = useState(false);
  const [avatarError, setAvatarError] = useState("");
  const [avatarSuccess, setAvatarSuccess] = useState("");
  const [showRating, setShowRating] = useState(false);
  const fileInput = useRef(null);
  async function uploadAvatar(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const validation = validateFile(file, true);
    setAvatarSuccess(""); setAvatarError(validation);
    if (validation) return;
    setAvatarPending(true);
    try {
      const body = new FormData(); body.append("file", file);
      setUser(await request("/profile/avatar", { method: "POST", body }));
      setAvatarSuccess("Photo updated in your profile, chat, reviews, and navigation.");
    } catch (err) { setAvatarError(err.message); }
    finally { setAvatarPending(false); }
  }
  async function submit(event) {
    event.preventDefault(); setPending(true); setError(""); setSuccess("");
    try { setUser(await request("/profile", { method: "PUT", body: form })); setSuccess("Profile saved. Your next recommendations will reflect your interests."); }
    catch (err) { setError(err.message); }
    finally { setPending(false); }
  }
  return <section className="page"><PageHeading eyebrow="MAKE IT YOURS" title="The traveler behind the trip."><div className="button-row"><button className="secondary" onClick={() => setShowRating((visible) => !visible)} aria-expanded={showRating}>Rate us <span aria-hidden="true">{"\u2605"}</span></button><button className="secondary" onClick={onLogout}>Log out</button></div></PageHeading>
    <div className="profile-layout"><aside className="profile-card"><img src="/cosy_pool_yaounde.jpg" alt="A peaceful pool in Yaounde" /><div className="profile-body"><Avatar user={user} className="large" /><h2>{user.full_name || user.username}</h2><p>@{user.username}</p>
      <input ref={fileInput} className="sr-only" type="file" accept={IMAGE_TYPES.join(",")} onChange={uploadAvatar} aria-label="Choose a new profile photo" disabled={avatarPending || pending} />
      <button className="secondary" disabled={avatarPending || pending} onClick={() => fileInput.current.click()}>{avatarPending ? "Updating photo..." : "Update profile image"}</button>
      <p className="data-note">Image under 5 MB. Cropped to a square and visible to other travelers. GIFs use their first frame.</p>
      <Feedback error={avatarError} success={avatarSuccess} />
      <p>{user.bio || "Every great trip starts with a little curiosity."}</p><div className="chips">{user.preferences.map((item) => <span className="chip" key={item}>{item}</span>)}</div></div></aside>
    <form className="panel form-stack" onSubmit={submit}><h2>Your travel profile</h2><p className="muted">Tell us what moves you. We'll find places that fit.</p>
      <label>Full name<input maxLength={80} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>
      <label>Home city<input maxLength={80} value={form.home_city} onChange={(e) => setForm({ ...form, home_city: e.target.value })} /></label>
      <label>About you<textarea maxLength={280} value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} placeholder="Mountains, museums, or the perfect meal?" /></label>
      <Interests value={form.preferences} onChange={(preferences) => setForm({ ...form, preferences })} />
      <Feedback error={error} success={success} /><button className="primary" disabled={pending || avatarPending}>{pending ? "Saving..." : "Save profile"}<Icon name="arrow" size={18} /></button>
    </form></div>
    {showRating && <AppRatingPanel />}
  </section>;
}

export function SharedPage({ shareId, navigate }) {
  const { data, loading, error, reload } = useData(`/shared/itineraries/${encodeURIComponent(shareId)}`);
  return <main className="shared-page"><a className="brand" href="#/discover"><Icon />globetrotter.</a><PageHeading eyebrow="A JOURNEY WORTH SHARING" title={data?.title || "Shared itinerary"} />
    <Feedback loading={loading} error={error} retry={reload} />
    {data && !error && <div className="panel"><p>{data.start_date || "Flexible dates"}{data.end_date && ` - ${data.end_date}`}</p><p className="preserve-text">{data.notes}</p><ol className="stops">{data.destinations.map((destination) => <li key={destination.id}><a href={`#/destination/${destination.id}`}><img src={destination.image} alt={destination.name} /></a><div><h3><a href={`#/destination/${destination.id}`}>{destination.name}</a></h3><p>{destination.city} / {destination.description}</p></div></li>)}</ol></div>}
    <button className="primary" onClick={() => navigate("discover")}>Plan your own adventure <Icon name="arrow" /></button>
  </main>;
}
