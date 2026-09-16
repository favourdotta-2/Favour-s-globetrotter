import { useEffect, useRef, useState } from "react";
import { MEDIA_TYPES, request, validateFile } from "../api";
import { Avatar, Feedback, Icon, PageHeading } from "../components";
import { ChatAttachment, emojis, Sticker, stickers } from "../chatMedia";

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
  const [picker, setPicker] = useState(null);
  const [sticker, setSticker] = useState(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const fileInput = useRef(null);
  const messageInput = useRef(null);
  const scrollArea = useRef(null);
  const shouldScroll = useRef(true);
  useEffect(() => {
    if (!file) { setPreview(""); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
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
    if (!text.trim() && !sticker && !file) { setSendError("Write a message or select a sticker, photo, or video."); return; }
    setPending(true); setSendError("");
    try {
      let message;
      if (file) {
        const body = new FormData(); body.append("file", file); body.append("text", text);
        message = await request("/chat/messages/upload", { method: "POST", body });
      } else {
        message = await request("/chat/messages", { method: "POST", body: { text, sticker } });
      }
      shouldScroll.current = true;
      setMessages((current) => mergeMessages(current, [message])); setText(""); setFile(null); setSticker(null); setPicker(null);
    } catch (error) { setSendError(error.message); }
    finally { setPending(false); }
  }
  function chooseFile(event) {
    const selected = event.target.files?.[0];
    event.target.value = "";
    if (!selected) return;
    const error = validateFile(selected);
    setSendError(error);
    if (!error) { setFile(selected); setSticker(null); setPicker(null); }
  }
  function insertEmoji(emoji) {
    const input = messageInput.current;
    const start = input.selectionStart ?? text.length;
    const end = input.selectionEnd ?? start;
    const next = `${text.slice(0, start)}${emoji}${text.slice(end)}`;
    if (next.length > 500) { setSendError("Your message cannot exceed 500 characters."); return; }
    setText(next); setPicker(null);
    input.focus();
  }
  return <section className="page"><PageHeading eyebrow="GOOD JOURNEYS. GREAT COMPANY." title="The travel lounge." />
    <div className="chat-layout"><div className="chat-panel"><header className="chat-header"><span className="brand-mark"><Icon name="chat" /></span><div><h2>Cameroon, together</h2><p>Community chat / refreshes every 5 seconds</p></div></header>
      <Feedback error={loadError} loading={loading} retry={() => setVersion((v) => v + 1)} />
      <div className="chat-messages" role="log" aria-label="Community messages" aria-live="polite" ref={scrollArea} onScroll={(e) => { const box = e.currentTarget; shouldScroll.current = box.scrollHeight - box.scrollTop - box.clientHeight < 70; }}>
        {!loading && !loadError && messages.length === 0 && <div className="empty-state"><Icon name="chat" size={40} /><h3>Every conversation starts with hello.</h3><p>Share a hidden gem or ask the community for a tip.</p></div>}
        {messages.map((message) => <article className={`message ${message.username === user.username ? "own" : ""}`} key={message.id}><Avatar user={message.username === user.username ? user : message.author || { username: message.username }} /><div><div className="message-meta"><strong>{message.username === user.username ? "You" : message.author?.full_name || message.username}</strong><time dateTime={message.created_at}>{new Date(message.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</time></div>
          {message.sticker && <Sticker id={message.sticker} />}
          {message.media && <ChatAttachment media={message.media} />}
          {message.text && <p>{message.text}</p>}
        </div></article>)}
      </div>
      <form className="chat-compose rich-compose" onSubmit={submit}><Feedback error={sendError} />
        <div className="chat-tools"><button type="button" className="secondary" disabled={pending} aria-expanded={picker === "emoji"} onClick={() => setPicker(picker === "emoji" ? null : "emoji")}>Emojis</button><button type="button" className="secondary" disabled={pending} aria-expanded={picker === "sticker"} onClick={() => setPicker(picker === "sticker" ? null : "sticker")}>Stickers</button><button type="button" className="secondary" disabled={pending} onClick={() => fileInput.current.click()}>Photo or video</button><input className="sr-only" type="file" accept={MEDIA_TYPES.join(",")} ref={fileInput} onChange={chooseFile} aria-label="Choose chat photo or video" disabled={pending} /></div>
        {picker === "emoji" && <div className="emoji-picker" aria-label="Choose an emoji">{emojis.map(([emoji, label]) => <button type="button" key={label} aria-label={label} onClick={() => insertEmoji(emoji)}>{emoji}</button>)}</div>}
        {picker === "sticker" && <div className="sticker-picker" aria-label="Choose a sticker">{stickers.map((item) => <button type="button" key={item.id} aria-label={`${item.label} sticker`} onClick={() => { setSticker(item.id); setFile(null); setPicker(null); }}><img src={item.image} alt="" /></button>)}</div>}
        {(sticker || file) && <div className="attachment-preview">{sticker && <Sticker id={sticker} />}{file && <div>{preview && (file.type.startsWith("video/") ? <video src={preview} controls preload="metadata" /> : <img src={preview} alt="Photo ready to send" />)}<small>{file.name} / {(file.size / 1_000_000).toFixed(2)} MB</small></div>}<button type="button" className="text-button" disabled={pending} onClick={() => { setSticker(null); setFile(null); }}>Remove attachment</button></div>}
        <label className="sr-only" htmlFor="message-input">Your message to the community</label><div className="compose-row"><input ref={messageInput} id="message-input" maxLength={500} disabled={pending} value={text} onChange={(e) => setText(e.target.value)} placeholder="A message, an emoji, a moment to share..." /><button className="primary" disabled={pending || (!text.trim() && !sticker && !file)}>{pending ? "Sending..." : "Send"}<Icon name="arrow" size={18} /></button></div><small className="muted">{text.length}/500 / Files strictly under 5 MB / Visible to every signed-in traveler</small></form>
    </div><aside className="lounge-note"><img src="/le_continent_restaurant.jpg" alt="A restaurant stop in Yaounde" /><div><p className="eyebrow">PULL UP A CHAIR</p><h2>The best tips come from fellow travelers.</h2><p>Share a place you loved. Ask about a route. Find a new perspective.</p><hr /><h3>A little lounge etiquette</h3><p>Be kind. Keep it travel-related. Never share passwords, private contact details, or sensitive travel plans here.</p><small>Showing the latest 100 community messages.</small></div></aside></div>
  </section>;
}
