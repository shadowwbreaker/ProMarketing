import { useEffect } from "react";

export function useLivePolling(load: () => Promise<void>, interval: number, event?: string, background = false) {
  useEffect(() => {
    let running = false;
    let pending = false;
    let stopped = false;
    let timer: number;
    async function refresh() {
      window.clearTimeout(timer);
      if (stopped || (document.hidden && !background)) return;
      if (running) {
        pending = true;
        return;
      }
      running = true;
      try {
        await load();
      } finally {
        running = false;
        if (!stopped && (!document.hidden || background)) {
          timer = window.setTimeout(refresh, pending ? 0 : document.hidden ? Math.max(8000, interval) : interval);
          pending = false;
        }
      }
    }
    void refresh();
    document.addEventListener("visibilitychange", refresh);
    window.addEventListener("focus", refresh);
    if (event) window.addEventListener(event, refresh);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", refresh);
      window.removeEventListener("focus", refresh);
      if (event) window.removeEventListener(event, refresh);
    };
  }, [load, interval, event, background]);
}
