"""Serve the main site (static) and /api/tweets (latest X tweets as JSON). Run from repo root with .env set."""
from pathlib import Path
import os
import sys

# Load .env from repo root (parent of scripts/)
REPO_ROOT = Path(__file__).resolve().parent.parent
_env = REPO_ROOT / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

from flask import Flask, send_from_directory, jsonify, request, redirect, abort

app = Flask(__name__, static_folder=str(REPO_ROOT), static_url_path="")


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/tweets")
def api_tweets():
    """Return latest tweets from life/x_posts.json (saved whenever Alder posts)."""
    import json
    posts_file = REPO_ROOT / "life" / "x_posts.json"
    tweets = []
    if posts_file.is_file():
        try:
            tweets = json.loads(posts_file.read_text(encoding="utf-8"))
        except Exception:
            tweets = []
    return jsonify({"tweets": tweets[:3]}), 200


def _load_products():
    import json
    pf = REPO_ROOT / "life" / "shop" / "products.json"
    if pf.is_file():
        try:
            return json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


@app.route("/api/products")
def api_products():
    """Return available digital products (no file paths exposed)."""
    products = _load_products()
    safe = []
    for p in products:
        safe.append({
            "id": p["id"],
            "name": p["name"],
            "description": p.get("description", ""),
            "price_cents": p["price_cents"],
        })
    return jsonify({"products": safe}), 200


@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    """Create a Stripe Checkout Session for a product."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe.api_key:
        return jsonify({"error": "Stripe not configured"}), 500

    data = request.get_json(force=True)
    product_id = data.get("product_id", "")
    products = _load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    base = request.host_url.rstrip("/")
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": product["price_cents"],
                "product_data": {"name": product["name"]},
            },
            "quantity": 1,
        }],
        mode="payment",
        metadata={"product_id": product_id},
        success_url=base + "/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=base + "/",
    )
    return jsonify({"url": session.url}), 200


@app.route("/success")
def success():
    """Verify payment and serve download link."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    session_id = request.args.get("session_id", "")
    if not session_id or not stripe.api_key:
        return redirect("/")
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return redirect("/")
    if session.payment_status != "paid":
        return redirect("/")
    product_id = session.metadata.get("product_id", "")
    products = _load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return redirect("/")
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Download - aldergrow</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>body{{font-family:"DM Serif Display",Georgia,serif;background:#f7f5f0;color:#2c2a26;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
.card{{background:#fff;border-radius:14px;box-shadow:0 2px 16px rgba(44,42,38,.07);padding:2.5rem;text-align:center;max-width:420px}}
a.btn{{display:inline-block;margin-top:1.5rem;padding:.75rem 2rem;background:#2c2a26;color:#fff;border-radius:8px;text-decoration:none;font-size:1rem}}
a.btn:hover{{background:#4a4740}}</style></head>
<body><div class="card"><h1>Thank you!</h1><p style="color:#5a5752;margin-top:1rem">Your purchase of <strong>{product['name']}</strong> is complete.</p>
<a class="btn" href="/download/{product_id}?session_id={session_id}">Download</a>
<p style="margin-top:1.5rem;font-size:.85rem;color:#8a8782"><a href="/" style="color:#6b6560">Back to aldergrow</a></p></div></body></html>"""


@app.route("/download/<product_id>")
def download(product_id):
    """Serve the digital file after verifying Stripe payment."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    session_id = request.args.get("session_id", "")
    if not session_id or not stripe.api_key:
        abort(403)
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        abort(403)
    if session.payment_status != "paid" or session.metadata.get("product_id") != product_id:
        abort(403)
    products = _load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product or not product.get("file"):
        abort(404)
    file_path = REPO_ROOT / "life" / product["file"]
    if not file_path.is_file():
        abort(404)
    return send_from_directory(str(file_path.parent), file_path.name, as_attachment=True)


def _load_reports():
    import json
    mf = REPO_ROOT / "life" / "reports" / "manifest.json"
    if mf.is_file():
        try:
            return json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _valid_promo_code(code: str) -> bool:
    """Check promo code. Override via PROMO_CODE env var."""
    expected = os.environ.get("PROMO_CODE", "aldercapital2026")
    return code and code.strip().lower() == expected.strip().lower()


@app.route("/api/verify-promo")
def api_verify_promo():
    """Verify promotional code for report access. Returns {access: true} if valid."""
    code = request.args.get("code", "")
    report_id = request.args.get("report_id", "")
    reports = _load_reports()
    report = next((r for r in reports if r.get("slug") == report_id), None)
    if not report_id or not report:
        return jsonify({"access": False}), 200
    if _valid_promo_code(code):
        return jsonify({"access": True}), 200
    return jsonify({"access": False}), 200


@app.route("/api/verify-report-access")
def api_verify_report_access():
    """Verify Stripe session_id grants access to report_id. Session ID = permanent token."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    session_id = request.args.get("session_id", "")
    report_id = request.args.get("report_id", "")
    if not session_id or not report_id or not stripe.api_key:
        return jsonify({"access": False}), 200
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        ok = (
            session.payment_status == "paid"
            and session.metadata.get("product_id") == report_id
        )
        return jsonify({"access": bool(ok)}), 200
    except Exception:
        return jsonify({"access": False}), 200


@app.route("/api/checkout-report", methods=["POST"])
def api_checkout_report():
    """Create Stripe Checkout Session for a research report. Redirects to report URL with token on success."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe.api_key:
        return jsonify({"error": "Stripe not configured"}), 500
    data = request.get_json(force=True)
    report_id = data.get("report_id", "")
    reports = _load_reports()
    report = next((r for r in reports if r.get("slug") == report_id), None)
    if not report:
        return jsonify({"error": "Report not found"}), 404
    base = request.host_url.rstrip("/")
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": report["price_cents"],
                "product_data": {"name": f"Research Report: {report['title']}"},
            },
            "quantity": 1,
        }],
        mode="payment",
        metadata={"product_id": report_id},
        success_url=base + f"/reports/{report_id}?token={{CHECKOUT_SESSION_ID}}",
        cancel_url=base + f"/reports/{report_id}",
    )
    return jsonify({"url": session.url}), 200


@app.route("/reports")
def reports_index():
    """List all research reports — premium dark theme matching report pages."""
    reports = _load_reports()
    items = []
    for r in reports:
        thesis = (r.get("thesis") or "")[:80]
        if thesis:
            thesis += "…"
        price = r.get("price_cents", 600) / 100
        items.append(
            f'<a href="/reports/{r["slug"]}" class="report-card">'
            f'<span class="report-ticker">{r.get("ticker", "")}</span>'
            f'<h3 class="report-title">{r["title"]}</h3>'
            f'<p class="report-thesis">{thesis}</p>'
            f'<span class="report-price">${price:.0f}</span>'
            f'</a>'
        )
    html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Research Reports — Alder Capital</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:ital,wght@0,400;0,500;0,600;0,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0a0b;--surface:#111113;--surface-2:#18181b;--border:#27272a;--text:#fafafa;--text-secondary:#a1a1aa;--text-muted:#71717a;--accent:#c8a24e;--serif:'DM Serif Display',Georgia,serif;--sans:'DM Sans',sans-serif;--mono:'JetBrains Mono',monospace}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:var(--sans);-webkit-font-smoothing:antialiased;min-height:100vh}
body::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");pointer-events:none;z-index:9999}
.topbar{border-bottom:1px solid var(--border);padding:16px 0}
.topbar-inner{max-width:720px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:center}
.brand{font-family:var(--mono);font-size:13px;letter-spacing:0.08em;color:var(--accent);text-transform:uppercase;font-weight:500}
.brand-sub{font-family:var(--mono);font-size:11px;color:var(--text-muted)}
.container{max-width:720px;margin:0 auto;padding:48px 24px}
h1{font-family:var(--serif);font-size:36px;margin-bottom:8px;letter-spacing:-0.02em}
.sub{font-family:var(--mono);font-size:12px;color:var(--text-muted);margin-bottom:40px}
.report-grid{display:grid;gap:24px}
.report-card{display:block;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:28px;text-decoration:none;color:inherit;transition:border-color .2s,box-shadow .2s}
.report-card:hover{border-color:var(--accent);box-shadow:0 0 0 1px rgba(200,162,78,0.2)}
.report-ticker{font-family:var(--mono);font-size:12px;letter-spacing:0.1em;color:var(--accent);text-transform:uppercase}
.report-title{font-family:var(--serif);font-size:22px;margin:8px 0 12px;line-height:1.3}
.report-thesis{color:var(--text-secondary);font-size:15px;line-height:1.6;margin-bottom:16px}
.report-price{font-family:var(--mono);font-size:18px;font-weight:500;color:var(--accent)}
.back{margin-top:48px;font-size:14px}.back a{color:var(--text-muted);text-decoration:none}.back a:hover{color:var(--accent)}
</style></head>
<body>
<div class="topbar"><div class="topbar-inner"><span class="brand">Alder Capital</span><span class="brand-sub">Independent Research</span></div></div>
<div class="container">
<h1>Research Reports</h1>
<p class="sub">Pay-per-view · Permanent access</p>
<div class="report-grid">""" + "".join(items) + """</div>
<p class="back"><a href="/">← Back to aldergrow</a></p>
</div></body></html>"""
    return html


@app.route("/reports/<slug>")
def report_page(slug):
    """Serve a research report HTML page (paywalled)."""
    reports_dir = REPO_ROOT / "life" / "reports"
    path = reports_dir / f"{slug}.html"
    if not path.is_file():
        abort(404)
    return send_from_directory(str(reports_dir), f"{slug}.html")


@app.route("/")
def index():
    return send_from_directory(REPO_ROOT, "index.html")


@app.route("/<path:path>")
def static_file(path):
    return send_from_directory(REPO_ROOT, path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
