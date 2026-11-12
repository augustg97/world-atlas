// The water rule, off the frame loop: the first run of it in a session takes most of a second (cold code) and
// every run a tenth of one, and the view should not stall for either. detail.js posts {id, g}; the answer goes back.
import { runRule } from './water.js?v=20261112T060955Z';

self.onmessage = (e) => {
  const { id, g } = e.data;
  try { const r = runRule(g); self.postMessage({ id, d: r.d, waterC: r.waterC, info: r.info }, [r.d.buffer]); }
  catch (err) { self.postMessage({ id, error: String((err && err.message) || err) }); }
};
