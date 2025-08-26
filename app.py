import os
import requests
from flask import Flask, request, Response, redirect, url_for
from urllib.parse import urljoin, urlparse

app = Flask(__name__)
session = requests.Session()

# Base URL of the site you want to proxy
TARGET_BASE = "https://discord.com"

def rewrite_links(content: str, base_url: str) -> str:
    """Naive HTML link rewrite so redirects stay inside the proxy"""
    if not content:
        return content
    return content.replace('href="/', f'href="/proxy/{base_url}/') \
                  .replace('src="/', f'src="/proxy/{base_url}/')

@app.route('/')
def index():
    return redirect("/proxy/https://discord.com/app")

@app.route('/proxy/<path:url>', methods=["GET", "POST"])
def proxy(url):
    target_url = url
    if not url.startswith("http"):
        target_url = "https://" + url

    if request.method == "POST":
        resp = session.post(
            target_url,
            data=request.form,
            headers={k: v for k, v in request.headers if k != "Host"},
            cookies=request.cookies,
        )
    else:
        resp = session.get(
            target_url,
            headers={k: v for k, v in request.headers if k != "Host"},
            cookies=request.cookies,
            stream=True,
        )

    # rewrite redirects to go through /proxy/
    if resp.is_redirect or resp.is_permanent_redirect:
        loc = resp.headers.get("Location", "")
        if loc:
            return redirect("/proxy/" + loc)

    content = resp.content
    if "text/html" in resp.headers.get("Content-Type", ""):
        content = rewrite_links(resp.text, target_url).encode("utf-8")

    excluded_headers = ["content-encoding", "transfer-encoding", "connection"]
    headers = [(name, value) for name, value in resp.raw.headers.items()
               if name.lower() not in excluded_headers]

    return Response(content, resp.status_code, headers)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
