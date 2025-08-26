# app.py
import os
import requests
import gzip
import brotli
from flask import Flask, request, Response, redirect
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus, unquote_plus

app = Flask(__name__)
session = requests.Session()

PROXY_PREFIX = "/proxy/"

# hop-by-hop headers we should not forward to the client
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade"
}

def decompress_if_needed(content_bytes: bytes, encoding: str):
    """Return decompressed bytes if encoding indicates gzip or br, else return original bytes."""
    if not encoding:
        return content_bytes
    enc = encoding.lower()
    if "gzip" in enc:
        try:
            return gzip.decompress(content_bytes)
        except Exception:
            return content_bytes
    if "br" in enc or "brotli" in enc:
        try:
            return brotli.decompress(content_bytes)
        except Exception:
            return content_bytes
    return content_bytes

def rewrite_html_links(html_text: str, base_url: str) -> str:
    """Rewrite anchors, forms, scripts, links, imgs, iframes so they route via proxy."""
    soup = BeautifulSoup(html_text, "html.parser")

    def proxify(abs_url: str):
        return f"{PROXY_PREFIX}{quote_plus(abs_url)}"

    # anchors
    for a in soup.find_all("a", href=True):
        try:
            full = urljoin(base_url, a["href"])
            a["href"] = proxify(full)
        except Exception:
            continue

    # forms
    for form in soup.find_all("form"):
        action = form.get("action") or base_url
        try:
            full = urljoin(base_url, action)
            form["action"] = proxify(full)
            # ensure method remains
        except Exception:
            form["action"] = proxify(base_url)

    # scripts, images, links, iframes
    for tag, attr in (("script", "src"), ("img", "src"), ("link", "href"), ("iframe", "src")):
        for t in soup.find_all(tag):
            if t.has_attr(attr):
                try:
                    full = urljoin(base_url, t[attr])
                    t[attr] = proxify(full)
                except Exception:
                    continue

    return str(soup)


def build_response_from_requests(resp, base_url):
    """Construct Flask Response from requests.Response with cookie and header handling."""
    # get raw bytes (requests auto-decodes gzip sometimes but not brotli)
    # use resp.content which is bytes; check Content-Encoding
    content_encoding = resp.headers.get("Content-Encoding", "")
    raw_bytes = resp.content
    # if encoding present and not handled by requests, decompress
    decoded = decompress_if_needed(raw_bytes, content_encoding)

    content_type = resp.headers.get("Content-Type", "")
    # If HTML, decode to text, rewrite links, then encode back to utf-8
    if content_type and "text/html" in content_type.lower():
        try:
            text = decoded.decode(resp.apparent_encoding or "utf-8", errors="replace")
        except Exception:
            text = decoded.decode("utf-8", errors="replace")
        new_text = rewrite_html_links(text, base_url)
        body = new_text.encode("utf-8")
        # ensure content-type charset is utf-8
        headers = [("Content-Type", "text/html; charset=utf-8")]
    else:
        body = decoded
        headers = []
        if content_type:
            headers.append(("Content-Type", content_type))

    # forward Set-Cookie headers separately (requests may combine them)
    # requests.Response.raw.headers may provide get_all; fallback to parsing header string
    set_cookie_values = []
    try:
        raw_headers = resp.raw.headers
        if hasattr(raw_headers, "get_all"):
            set_cookie_values = raw_headers.get_all("Set-Cookie") or []
        else:
            # fallback: check resp.headers for 'Set-Cookie' (may be combined)
            sc = resp.headers.get("Set-Cookie")
            if sc:
                set_cookie_values = [sc]
    except Exception:
        sc = resp.headers.get("Set-Cookie")
        if sc:
            set_cookie_values = [sc]

    # copy other headers (excluding hop-by-hop and content-encoding)
    for name, value in resp.headers.items():
        lname = name.lower()
        if lname in HOP_BY_HOP or lname == "content-encoding":
            continue
        if name.lower() == "set-cookie":
            continue
        headers.append((name, value))

    # append Set-Cookie entries as separate headers
    for sc in set_cookie_values:
        headers.append(("Set-Cookie", sc))

    return Response(body, status=resp.status_code, headers=headers)


@app.route(PROXY_PREFIX + "<path:raw_url>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
def proxy(raw_url):
    # raw_url is percent-encoded by our rewrite; decode
    target = unquote_plus(raw_url)
    if not target.startswith("http"):
        # default to https
        target = "https://" + target

    # Build headers to forward (strip Host)
    forward_headers = {}
    for k, v in request.headers.items():
        if k.lower() in ("host",):
            continue
        # Optionally remove Accept-Encoding so upstream returns uncompressed OR we handle it
        # We'll accept compressed but will decompress later.
        forward_headers[k] = v

    try:
        if request.method in ("POST", "PUT", "PATCH"):
            data = request.get_data()
            resp = session.request(request.method, target, headers=forward_headers, data=data, allow_redirects=False, cookies=request.cookies, timeout=30)
        else:
            resp = session.request(request.method, target, headers=forward_headers, params=request.args, allow_redirects=False, cookies=request.cookies, timeout=30)
    except requests.RequestException as e:
        return f"Upstream request failed: {e}", 502

    # Handle redirects -> keep inside proxy
    if resp.is_redirect or resp.is_permanent_redirect:
        loc = resp.headers.get("Location", "")
        if loc:
            # make absolute URL
            abs_loc = urljoin(target, loc)
            proxied = PROXY_PREFIX + quote_plus(abs_loc)
            return redirect(proxied, code=302)

    return build_response_from_requests(resp, base_url=target)


@app.route("/")
def index():
    return """
    <h3>Python Proxy (Railway)</h3>
    <form action="/proxy/" method="get">
      <input name="url" placeholder="https://discord.com/app" style="width:400px"/>
      <button type="submit">Go</button>
    </form>
    <p>Note: heavy JS/websocket features may still need a more advanced proxy/tunneler.</p>
    """

@app.route("/proxy/")
def proxy_root():
    url = request.args.get("url")
    if not url:
        return "No url", 400
    return redirect(PROXY_PREFIX + quote_plus(url))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
