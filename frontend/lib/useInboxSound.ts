import { useCallback, useEffect, useRef, useState } from "react";
import type { InboxStatus } from "@/lib/api/chat";

const setting = "pm-inbox-sound";

export function useInboxSound(userId: string) {
  const context = useRef<AudioContext | null>(null);
  const previous = useRef<InboxStatus["signals"] | null>(null);
  const [enabled, setEnabled] = useState(false);
  const enabledRef = useRef(false);
  const unlock = useCallback(() => {
    if (!window.AudioContext) return;
    context.current ??= new AudioContext();
    void context.current.resume().catch(() => {});
  }, []);

  useEffect(() => {
    previous.current = null;
    if (!userId) return;
    const sync = () => {
      enabledRef.current = localStorage.getItem(setting) === "on";
      setEnabled(enabledRef.current);
    };
    const gesture = () => { if (enabledRef.current) unlock(); };
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener("pointerdown", gesture);
    window.addEventListener("keydown", gesture);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("pointerdown", gesture);
      window.removeEventListener("keydown", gesture);
      void context.current?.close().catch(() => {});
      context.current = null;
    };
  }, [unlock, userId]);

  function toggle() {
    enabledRef.current = !enabledRef.current;
    setEnabled(enabledRef.current);
    localStorage.setItem(setting, enabledRef.current ? "on" : "off");
    if (enabledRef.current) unlock();
  }

  const announce = useCallback((signals: InboxStatus["signals"]) => {
    const last = previous.current;
    previous.current = signals;
    const audio = context.current;
    if (!last || !enabledRef.current || audio?.state !== "running") return;
    const changed = (["order", "message"] as const).filter((kind) => signals[kind] && signals[kind] !== last[kind]);
    const key = (kind: string) => `${setting}:${userId}:${kind}`;
    const pending = changed.filter((kind) => localStorage.getItem(key(kind)) !== signals[kind]);
    if (!pending.length) return;
    for (const kind of pending) localStorage.setItem(key(kind), signals[kind]!);
    const notes = pending.includes("order") ? [659, 880] : [740];
    notes.forEach((frequency, index) => {
      const oscillator = audio.createOscillator();
      const volume = audio.createGain();
      const start = audio.currentTime + index * 0.12;
      oscillator.frequency.value = frequency;
      volume.gain.setValueAtTime(0.001, start);
      volume.gain.exponentialRampToValueAtTime(0.15, start + 0.02);
      volume.gain.exponentialRampToValueAtTime(0.001, start + 0.2);
      oscillator.connect(volume).connect(audio.destination);
      oscillator.start(start);
      oscillator.stop(start + 0.22);
      oscillator.onended = () => { oscillator.disconnect(); volume.disconnect(); };
    });
  }, [userId]);

  return { enabled, toggle, announce };
}
