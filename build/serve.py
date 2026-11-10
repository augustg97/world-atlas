#!/usr/bin/env python3
"""Local development server for web/: plain static files with caching switched off, so an edit
or a rebuilt field is what the next reload shows (TRAPS D2: stale data looks like a failed build).
    python3 build/serve.py [port]
"""
import http.server, os, sys

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()
    def log_message(self, *a):
        pass

    def do_POST(self):
        # Development only: the page posts canvas.toDataURL() here so a frame can be inspected at
        # full resolution (WORKING-RULES 1: verify by looking). Written to scratchpad/, gitignored.
        if not self.path.startswith("/__shot/"):
            self.send_error(404); return
        import base64, re
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", self.path[len("/__shot/"):]) or "frame.png"
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        out = os.path.join(SHOTS, name)
        os.makedirs(SHOTS, exist_ok=True)
        open(out, "wb").write(base64.b64decode(body.split(",", 1)[1]))
        self.send_response(200); self.end_headers(); self.wfile.write(out.encode())

SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scratchpad")

if __name__ == "__main__":
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web"))
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8150
    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
