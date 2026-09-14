import { useState } from "react";
import { request, useData } from "../api";
import { Feedback, Icon, Interests, PageHeading } from "../components";

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

export function ProfilePage({ user, setUser }) {
  const [form, setForm] = useState({ full_name: user.full_name, preferences: user.preferences, bio: user.bio, home_city: user.home_city });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  async function submit(event) {
    event.preventDefault(); setPending(true); setError(""); setSuccess("");
    try { setUser(await request("/profile", { method: "PUT", body: form })); setSuccess("Profile saved. Your next recommendations will reflect your interests."); }
    catch (err) { setError(err.message); }
    finally { setPending(false); }
  }
  return <section className="page"><PageHeading eyebrow="MAKE IT YOURS" title="The traveler behind the trip." />
    <div className="profile-layout"><aside className="profile-card"><img src="/cosy_pool_yaounde.jpg" alt="A peaceful pool in Yaounde" /><div className="profile-body"><span className="avatar large">{user.username[0].toUpperCase()}</span><h2>{user.full_name || user.username}</h2><p>@{user.username}</p><p>{user.bio || "Every great trip starts with a little curiosity."}</p><div className="chips">{user.preferences.map((item) => <span className="chip" key={item}>{item}</span>)}</div></div></aside>
    <form className="panel form-stack" onSubmit={submit}><h2>Your travel profile</h2><p className="muted">Tell us what moves you. We'll find places that fit.</p>
      <label>Full name<input maxLength={80} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>
      <label>Home city<input maxLength={80} value={form.home_city} onChange={(e) => setForm({ ...form, home_city: e.target.value })} /></label>
      <label>About you<textarea maxLength={280} value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} placeholder="Mountains, museums, or the perfect meal?" /></label>
      <Interests value={form.preferences} onChange={(preferences) => setForm({ ...form, preferences })} />
      <Feedback error={error} success={success} /><button className="primary" disabled={pending}>{pending ? "Saving..." : "Save profile"}<Icon name="arrow" size={18} /></button>
    </form></div>
  </section>;
}

export function SharedPage({ shareId, navigate }) {
  const { data, loading, error, reload } = useData(`/shared/itineraries/${encodeURIComponent(shareId)}`);
  return <main className="shared-page"><a className="brand" href="#/discover"><Icon />globetrotter.</a><PageHeading eyebrow="A JOURNEY WORTH SHARING" title={data?.title || "Shared itinerary"} />
    <Feedback loading={loading} error={error} retry={reload} />
    {data && !error && <div className="panel"><p>{data.start_date || "Flexible dates"}{data.end_date && ` - ${data.end_date}`}</p><p className="preserve-text">{data.notes}</p><ol className="stops">{data.destinations.map((destination) => <li key={destination.id}><img src={destination.image} alt={destination.name} /><div><h3>{destination.name}</h3><p>{destination.city} / {destination.description}</p></div></li>)}</ol></div>}
    <button className="primary" onClick={() => navigate("discover")}>Plan your own adventure <Icon name="arrow" /></button>
  </main>;
}
