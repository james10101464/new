import requests
from flask import Flask, request, Response, redirect
from urllib.parse import urljoin, urlparse

app = Flask(__name__)
session = requests.Session()

PROXY_PREFIX = "/proxy/"

def rewrite_links(content, base_url):
    """
    Rewrites <a>, <link>, <script>, <img>, and other URLs so that
    they continue to pass through the proxy.
    """
    if not content:
        return content

    content = content.replace("https://", PROXY_PREFIX + "https://")
    content = content.replace("http://", PROXY_PREFIX + "http://")

    return content

@app.route(PROXY_PREFIX + "<path:url>", methods=["GET", "POST"])
def proxy(url):
    target_url = url if url.startswith("http") else "https://" + url

    try:
        if request.method == "POST":
            resp = session.post(
                target_url,
                data=request.form,
                headers={k: v for k, v in request.headers if k.lower() != "host"},
                cookies=request.cookies,
            )
        else:
            resp = session.get(
                target_url,
                headers={k: v for k, v in request.headers if k.lower() != "host"},
                cookies=request.cookies,
            )
    except Exception as e:
        return f"Proxy request failed: {e}", 502

    # Handle redirects → stay inside proxy
    if resp.is_redirect or resp.is_permanent_redirect:
        loc = resp.headers.get("Location", "")
        if loc:
            return redirect(PROXY_PREFIX + loc)

    # Content (requests auto-decompresses gzip/br)
    content = resp.content
    if "text/html" in resp.headers.get("Content-Type", ""):
        content = rewrite_links(resp.text, target_url).encode("utf-8")

    # Filter headers
    excluded_headers = ["content-encoding", "transfer-encoding", "connection"]
    headers = [(name, value) for name, value in resp.headers.items()
               if name.lower() not in excluded_headers]

    return Response(content, resp.status_code, headers)

@app.route("/")
def home():
    return """
    <h2>Python Proxy (Railway)</h2>
    <form action="/proxy/" method="get">
        <input name="url" placeholder="Enter URL" style="width:300px"/>
        <button type="submit">Go</button>
    </form>
    """

@app.route("/proxy/")
def proxy_home():
    url = request.args.get("url")
    if not url:
        return "No URL given", 400
    return redirect(PROXY_PREFIX + url)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
