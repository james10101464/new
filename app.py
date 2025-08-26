from flask import Flask, request, Response
import requests
import os

app = Flask(__name__)

@app.route("/")
def index():
    return '''
    <h2>Python Web Proxy</h2>
    <form method="get" action="/proxy">
      <input type="text" name="url" placeholder="Enter URL" style="width:300px;">
      <button type="submit">Go</button>
    </form>
    '''

@app.route("/proxy")
def proxy():
    url = request.args.get("url")
    if not url:
        return "No URL provided", 400
    if not url.startswith("http"):
        url = "http://" + url

    try:
        resp = requests.get(url)
        excluded = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded]
        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return f"Error fetching {url}: {e}", 502

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Railway assigns PORT
    app.run(host="0.0.0.0", port=port, debug=True)
