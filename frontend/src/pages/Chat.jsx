import { useEffect, useRef, useState } from "react";
import { request } from "../api";
import { Feedback, Icon, PageHeading } from "../components";

function mergeMessages(current, incoming) {
  const messages = new Map([...current, ...incoming].map((message) => [message.id, message]));
  return [...messages.values()].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)).slice(-100);
}

export default function ChatPage({ user }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [sendError, setSendError] = useState("");
  const [pending, setPending] = useState(false);
  const [version, setVersion] = useState(0);
  const scrollArea = useRef(null);
  const shouldScroll = useRef(true);
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    async function load() {
      try {
        const incoming = await request("/chat/messages", { signal: controller.signal });
        if (!controller.signal.aborted) { setMessages((current) => mergeMessages(current, incoming)); setLoadError(""); }
      } catch (error) {
        if (!controller.signal.aborted) setLoadError(error.message);
      } finally {
        if (!controller.signal.aborted) { setLoading(false); timer = setTimeout(load, 5000); }
      }
    }
    load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [version]);
  useEffect(() => {
    if (shouldScroll.current && scrollArea.current) scrollArea.current.scrollTop = scrollArea.current.scrollHeight;
  }, [messages]);
  async function submit(event) {
    event.preventDefault();
    if (!text.trim()) { setSendError("Write a message before sending."); return; }
    setPending(true); setSendError("");
    try {
      const message = await request("/chat/messages", { method: "POST", body: { text } });
      shouldScroll.current = true;
      setMessages((current) => mergeMessages(current, [message])); setText("");
    } catch (error) { setSendError(error.message); }
    finally { setPending(false); }
  }
  return <section className="page"><PageHeading eyebrow="GOOD JOURNEYS. GREAT COMPANY." title="The travel lounge." />
    <div className="chat-layout"><div className="chat-panel"><header className="chat-header"><span className="brand-mark"><Icon name="chat" /></span><div><h2>Cameroon, together</h2><p>Community chat / refreshes every 5 seconds</p></div></header>
      <Feedback error={loadError} loading={loading} retry={() => setVersion((v) => v + 1)} />
      <div className="chat-messages" role="log" aria-label="Community messages" aria-live="polite" ref={scrollArea} onScroll={(e) => { const box = e.currentTarget; shouldScroll.current = box.scrollHeight - box.scrollTop - box.clientHeight < 70; }}>
        {!loading && !loadError && messages.length === 0 && <div className="empty-state"><Icon name="chat" size={40} /><h3>Every conversation starts with hello.</h3><p>Share a hidden gem or ask the community for a tip.</p></div>}
        {messages.map((message) => <article className={`message ${message.username === user.username ? "own" : ""}`} key={message.id}><span className="avatar">{message.username[0].toUpperCase()}</span><div><div className="message-meta"><strong>{message.username === user.username ? "You" : message.username}</strong><time dateTime={message.created_at}>{new Date(message.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</time></div><p>{message.text}</p></div></article>)}
      </div>
      <form className="chat-compose" onSubmit={submit}><Feedback error={sendError} /><label className="sr-only" htmlFor="message-input">Your message to the community</label><div><input id="message-input" required maxLength={500} disabled={pending} value={text} onChange={(e) => setText(e.target.value)} placeholder="A question, a hidden gem, a friendly hello..." /><button className="primary" disabled={pending || !text.trim()}>{pending ? "Sending..." : "Send"}<Icon name="arrow" size={18} /></button></div><small className="muted">{text.length}/500 / Visible to every signed-in traveler</small></form>
    </div><aside className="lounge-note"><img src="/le_continent_restaurant.jpg" alt="A restaurant stop in Yaounde" /><div><p className="eyebrow">PULL UP A CHAIR</p><h2>The best tips come from fellow travelers.</h2><p>Share a place you loved. Ask about a route. Find a new perspective.</p><hr /><h3>A little lounge etiquette</h3><p>Be kind. Keep it travel-related. Never share passwords, private contact details, or sensitive travel plans here.</p><small>Showing the latest 100 community messages.</small></div></aside></div>
  </section>;
}
