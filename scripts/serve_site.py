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


@app.route("/")
def index():
    return send_from_directory(REPO_ROOT, "index.html")


@app.route("/<path:path>")
def static_file(path):
    return send_from_directory(REPO_ROOT, path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
