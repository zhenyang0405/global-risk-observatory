// Lightweight EventSource subscription with auto-reconnect.

export type SSEHandler<T> = (payload: T) => void;

export function subscribe<T>(
  url: string,
  onMessage: SSEHandler<T>,
  onError?: (e: Event) => void
): () => void {
  let closed = false;
  let es: EventSource | null = null;
  let reconnectDelay = 1000;

  const open = () => {
    if (closed) return;
    es = new EventSource(url);
    es.onmessage = (evt) => {
      reconnectDelay = 1000;
      try {
        const data = JSON.parse(evt.data) as T;
        onMessage(data);
      } catch {
        // ignore malformed lines (keepalives etc.)
      }
    };
    es.onerror = (e) => {
      if (onError) onError(e);
      es?.close();
      es = null;
      if (closed) return;
      setTimeout(open, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 1.5, 15000);
    };
  };

  open();
  return () => {
    closed = true;
    es?.close();
  };
}
