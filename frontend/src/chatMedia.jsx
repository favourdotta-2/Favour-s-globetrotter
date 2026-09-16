import { useEffect, useRef, useState } from "react";
import { request } from "./api";
import { Feedback } from "./components";
import hello from "./assets/stickers/hello.svg";
import adventure from "./assets/stickers/adventure.svg";
import loveCameroon from "./assets/stickers/love-cameroon.svg";
import letsGo from "./assets/stickers/lets-go.svg";

export const stickers = [
  { id: "hello", label: "Hey traveler", image: hello },
  { id: "adventure", label: "Adventure", image: adventure },
  { id: "love-cameroon", label: "Love Cameroon", image: loveCameroon },
  { id: "lets-go", label: "Let's go", image: letsGo },
];
export const emojis = [
  ["\u{1F44B}", "Wave"], ["\u{1F60A}", "Smile"], ["\u{1F60D}", "Heart eyes"],
  ["\u{1F44D}", "Thumbs up"], ["\u{1F389}", "Celebration"], ["\u{1F30D}", "Globe"],
  ["\u{1F3D4}", "Mountain"], ["\u{1F4F8}", "Camera"], ["\u{1F49A}", "Green heart"],
  ["\u{1F602}", "Laugh"], ["\u{1F64C}", "Raised hands"], ["\u{2708}\u{FE0F}", "Airplane"],
];

export function Sticker({ id }) {
  const sticker = stickers.find((item) => item.id === id);
  return sticker ? <img className="chat-sticker" src={sticker.image} alt={`${sticker.label} sticker`} /> : <p>Sticker unavailable.</p>;
}

export function ChatAttachment({ media }) {
  const [visible, setVisible] = useState(false);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const container = useRef(null);
  useEffect(() => {
    if (media.kind !== "image") return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) { setVisible(true); observer.disconnect(); }
    });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, [media.id, media.kind]);
  useEffect(() => {
    if (!visible) return;
    const controller = new AbortController();
    let objectUrl;
    setError("");
    request(`/chat/media/${media.id}`, { responseType: "blob", signal: controller.signal })
      .then((blob) => {
        if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); }
      }).catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [visible, media.id, version]);
  return <div className="chat-attachment" ref={container}>
    {!visible && <button className="secondary" type="button" onClick={() => setVisible(true)}>{media.kind === "video" ? "Load video" : "View photo"} / {(media.size / 1_000_000).toFixed(2)} MB</button>}
    {visible && !url && !error && <small role="status">Loading attachment...</small>}
    {url && (media.kind === "video" ? <video src={url} controls preload="metadata" aria-label={media.name} onError={() => setError("This browser could not play the video.")} /> : <img src={url} alt={media.name} onError={() => setError("This photo could not be displayed.")} />)}
    <Feedback error={error} retry={() => { setUrl(""); setVersion((value) => value + 1); }} />
    <small>{media.name}</small>
  </div>;
}
