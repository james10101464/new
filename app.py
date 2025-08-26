import http.server
import os

PORT = int(os.environ.get("PORT", 8080))

handler = http.server.SimpleHTTPRequestHandler
server = http.server.HTTPServer(("0.0.0.0", PORT), handler)

print(f"Server running on port {PORT}")
server.serve_forever()
