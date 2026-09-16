import { lazy, Suspense, useEffect, useState } from "react";
import { request, TOKEN_KEY } from "./api";
import { Avatar, Feedback, Icon } from "./components";
import { AuthPage, ProfilePage, SharedPage } from "./pages/Account";
import DiscoverPage from "./pages/Discover";
import ItineraryPage, { emptyDraft } from "./pages/Itinerary";
import ChatPage from "./pages/Chat";
import DestinationPage from "./pages/Destination";
import "./social.css";

const MapPage = lazy(() => import("./pages/Map"));

const navigation = [
  ["discover", "Discover", "compass"],
  ["itinerary", "My itineraries", "trip"],
  ["map", "Explore map", "map"],
  ["chat", "Travel lounge", "chat"],
  ["profile", "My profile", "user"],
];
const readRoute = () => window.location.hash.slice(2) || "discover";

export default function App() {
  const [route, setRoute] = useState(readRoute);
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(Boolean(localStorage.getItem(TOKEN_KEY)));
  const [sessionError, setSessionError] = useState("");
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState(emptyDraft);
  const [sessionVersion, setSessionVersion] = useState(0);
  const navigate = (path) => { window.location.hash = `/${path}`; };

  useEffect(() => {
    const changed = () => setRoute(readRoute());
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);

  function logout(message = "") {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem("globetrotter_user");
    setUser(null);
    setDraft(emptyDraft());
    setNotice(message);
    navigate("login");
  }

  useEffect(() => {
    const expire = () => logout("Your session has expired. Please log in again.");
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    const controller = new AbortController();
    setChecking(true);
    setSessionError("");
    request("/auth/me", { signal: controller.signal }).then((profile) => {
      if (!controller.signal.aborted && localStorage.getItem(TOKEN_KEY) === token) setUser(profile);
    }).catch((error) => {
      if (!controller.signal.aborted && localStorage.getItem(TOKEN_KEY) === token) setSessionError(error.message);
    }).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, [sessionVersion]);

  useEffect(() => {
    const changed = (event) => {
      if (event.key === "globetrotter_profile_version" && localStorage.getItem(TOKEN_KEY)) {
        setSessionVersion((version) => version + 1);
      }
    };
    window.addEventListener("storage", changed);
    return () => window.removeEventListener("storage", changed);
  }, []);

  function updateUser(profile) {
    setUser(profile);
    localStorage.setItem("globetrotter_profile_version", String(Date.now()));
  }

  function login(auth) {
    localStorage.setItem(TOKEN_KEY, auth.token);
    setUser(auth.user);
    setNotice("");
    setSessionError("");
    navigate("discover");
  }

  function addDestination(destination) {
    setDraft((current) => current.destination_ids.includes(destination.id) ? current : {
      ...current, destination_ids: [...current.destination_ids, destination.id],
    });
    setNotice(`${destination.name} added to your itinerary draft.`);
  }

  if (route.startsWith("shared/")) return <SharedPage shareId={route.slice(7)} navigate={navigate} />;
  if (checking && !user) return <div className="session-screen"><Icon size={44} /><Feedback loading /></div>;
  if (sessionError && !user) return <div className="session-screen"><Feedback error={sessionError} retry={() => setSessionVersion((v) => v + 1)} /><button className="secondary" onClick={() => logout()}>Return to login</button></div>;
  if (!user) return <AuthPage mode={route === "signup" ? "signup" : "login"} navigate={navigate} onSuccess={login} notice={notice} />;
  const destinationId = route.startsWith("destination/") ? route.slice(12) : null;
  const active = navigation.some(([id]) => id === route) ? route : "discover";

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#/discover"><span className="brand-mark"><Icon /></span>globetrotter<span className="brand-dot">.</span></a>
      <p className="sidebar-caption">A LITTLE CURIOSITY. A BIG WORLD.</p>
      <nav aria-label="Main navigation">{navigation.map(([id, label, icon]) =>
        <a key={id} href={`#/${id}`} className={active === id ? "active" : ""} aria-current={active === id ? "page" : undefined}><Icon name={icon} />{label}
          {id === "itinerary" && draft.destination_ids.length > 0 && <span className="count">{draft.destination_ids.length}</span>}
        </a>)}</nav>
      <div className="sidebar-note"><Icon name="pin" /><h3>Closer to home.<br />Further from ordinary.</h3><p>Rediscover the beauty of Cameroon, one trip at a time.</p><a href="#/map">Find your way <Icon name="arrow" size={16} /></a></div>
      <div className="sidebar-user"><Avatar user={user} /><div><strong>{user.full_name || user.username}</strong><small>Curious traveler</small></div><button className="text-button" onClick={() => logout()}>Log out</button></div>
    </aside>
    <main className="main-content">
      <header className="topbar"><span>Cameroon, through a different lens</span><span className="edition"><span className="status-dot" /> The Cameroon collection</span></header>
      {sessionError && <Feedback error={sessionError} retry={() => setSessionVersion((v) => v + 1)} />}
      {notice && <div className="notice" role="status">{notice}<button aria-label="Dismiss notification" onClick={() => setNotice("")}>&times;</button></div>}
      {destinationId && <DestinationPage key={destinationId} destinationId={destinationId} user={user} draft={draft} onAdd={addDestination} />}
      {active === "discover" && !destinationId && <DiscoverPage user={user} draft={draft} onAdd={addDestination} />}
      {active === "itinerary" && <ItineraryPage draft={draft} setDraft={setDraft} navigate={navigate} />}
      {active === "map" && <Suspense fallback={<Feedback loading />}><MapPage draft={draft} onAdd={addDestination} /></Suspense>}
      {active === "chat" && <ChatPage user={user} />}
      {active === "profile" && <ProfilePage user={user} setUser={updateUser} onLogout={() => logout()} />}
      <footer>Made for the journey, not just the destination. <span>GlobeTrotter / Cameroon</span></footer>
    </main>
  </div>;
}
