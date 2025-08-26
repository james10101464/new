import http.server
import urllib.request
import os

PORT = int(os.environ.get("PORT", 8080))

class Proxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Build full URL
            host = self.headers.get("Host")
            if not host:
                self.send_error(400, "No Host header")
                return

            url = f"http://{host}{self.path}"
            print(f"Fetching: {url}")

            with urllib.request.urlopen(url) as resp:
                self.send_response(resp.status)
                for header, value in resp.getheaders():
                    if header.lower() != "transfer-encoding":
                        self.send_header(header, value)
                self.end_headers()
                self.wfile.write(resp.read())

        except Exception as e:
            self.send_error(502, f"Proxy error: {e}")

    def do_CONNECT(self):
        # Browsers need this for HTTPS sites
        self.send_error(501, "HTTPS CONNECT not implemented yet")

if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Proxy)
    print(f"Proxy server running on port {PORT}")
    server.serve_forever()
