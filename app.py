import http.server
import urllib.request
import os

# Railway provides the port in the PORT environment variable
PORT = int(os.environ.get("PORT", 8080))

class Proxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            url = self.path
            if not url.startswith("http"):
                url = "http://" + url

            print(f"Fetching: {url}")
            with urllib.request.urlopen(url) as response:
                self.send_response(response.status)
                for header, value in response.getheaders():
                    if header.lower() != "transfer-encoding":
                        self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.read())
        except Exception as e:
            self.send_error(502, f"Proxy error: {e}")

    def do_POST(self):
        self.send_error(405, "POST not supported in this proxy")

if __name__ == "__main__":
    server_address = ("0.0.0.0", PORT)  # important for Railway
    httpd = http.server.HTTPServer(server_address, Proxy)
    print(f"Proxy running on port {PORT}")
    httpd.serve_forever()
