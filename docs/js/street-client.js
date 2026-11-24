// Both the street texture and 3D buildings share one vector tile worker and its decoded cache.
export class StreetWorker {
  constructor() {
    this.pending = new Map();
    this.nextId = 0;
  }

  request(message, signal) {
    if (signal.aborted) return Promise.reject(new DOMException('aborted', 'AbortError'));
    try { this.worker ||= this.start(); }
    catch (error) { return Promise.reject(error); }
    const id = ++this.nextId, worker = this.worker;
    return new Promise((resolve, reject) => {
      const finish = (error, data) => {
        this.pending.delete(id);
        signal.removeEventListener('abort', abort);
        if (error) reject(error); else resolve(data);
      };
      const abort = () => {
        worker.postMessage({ cancel: id });
        finish(new DOMException('aborted', 'AbortError'));
      };
      this.pending.set(id, finish);
      signal.addEventListener('abort', abort, { once: true });
      worker.postMessage({ ...message, id });
    });
  }

  start() {
    const url = new URL('./streets.worker.js', import.meta.url);
    url.search = new URL(import.meta.url).search;
    const worker = new Worker(url, { type: 'module' });
    worker.onmessage = ({ data }) => {
      const finish = this.pending.get(data.id);
      if (!finish) { data.overlay?.close(); data.pattern?.close(); return; }
      const error = data.error === 'aborted' ? new DOMException('aborted', 'AbortError') : data.error && new Error(data.error);
      finish(error, data);
    };
    worker.onerror = () => {
      worker.terminate();
      this.worker = null;
      for (const finish of this.pending.values()) finish(new Error('The streets worker failed.'));
    };
    return worker;
  }
}
