"""Local auth-injecting proxy, for headless screenshots only.

WHY: the terminal sits behind HTTP Basic auth. Putting credentials in the URL
makes Chrome expose them to page JavaScript, which then breaks every fetch
("Request cannot be constructed from a URL that includes credentials") -- so a
naive screenshot shows a broken page and I learn nothing.

This listens on localhost, adds the Authorization header for you, and forwards
to the real site. Chrome then sees a clean http://127.0.0.1 origin with no
credentials in the URL, exactly like a normal browser session.

Not part of the product. Throwaway tooling, never served, never committed.
"""
import base64
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "http://140.238.226.249:8000"
AUTH = "Basic " + base64.b64encode(b"ankit:ankitc21").decode()
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8899

HOP = {"connection", "keep-alive", "transfer-encoding", "upgrade",
       "proxy-authenticate", "proxy-authorization", "te", "trailer"}


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass  # quiet

    def _forward(self, method):
        url = UPSTREAM + self.path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP and k.lower() != "authorization"
                   and k.lower() != "host"}
        headers["Authorization"] = AUTH
        headers["Host"] = "140.238.226.249:8000"

        req = urllib.request.Request(url, data=body, headers=headers,
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
                self.send_response(r.status)
                for k, v in r.headers.items():
                    if k.lower() not in HOP and k.lower() != "content-length":
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            msg = f"proxy error: {e}".encode()
            self.send_response(502)
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def do_HEAD(self):
        self._forward("HEAD")


if __name__ == "__main__":
    print(f"proxy on http://127.0.0.1:{PORT} -> {UPSTREAM}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Proxy).serve_forever()
