import os
import stripe
from flask import Flask, request, jsonify

app = Flask(__name__)

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

# Map each Stripe price ID to an internal plan name.
# Replace these with the actual price IDs from your Stripe dashboard
# (Dashboard → Products → select the price → copy "API ID", e.g. price_1ABC...).
# Payment link slugs (buy.stripe.com/...) are NOT the same as price IDs.
PRICE_PLAN_MAP = {
    # Standard — Monthly
    os.environ.get("PRICE_STD_MONTHLY", "price_std_monthly_placeholder"):   "standard",
    # Standard — 6-month
    os.environ.get("PRICE_STD_6MONTH",  "price_std_6month_placeholder"):    "standard",
    # Standard — Annual
    os.environ.get("PRICE_STD_ANNUAL",  "price_std_annual_placeholder"):    "standard",
    # White Label — Monthly
    os.environ.get("PRICE_WL_MONTHLY",  "price_wl_monthly_placeholder"):    "white_label",
    # White Label — 6-month
    os.environ.get("PRICE_WL_6MONTH",   "price_wl_6month_placeholder"):     "white_label",
    # White Label — Annual
    os.environ.get("PRICE_WL_ANNUAL",   "price_wl_annual_placeholder"):     "white_label",
}


def get_plan_for_session(session):
    """Return the plan name for a completed checkout session, or None."""
    line_items = stripe.checkout.Session.list_line_items(session["id"], limit=1)
    if not line_items.data:
        return None
    price_id = line_items.data[0].price.id
    return PRICE_PLAN_MAP.get(price_id)


@app.route("/webhook/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        plan = get_plan_for_session(session)
        if plan:
            customer_email = session.get("customer_details", {}).get("email")
            customer_id = session.get("customer")
            handle_new_subscription(customer_email, customer_id, plan, session)

    return jsonify({"status": "ok"}), 200


def handle_new_subscription(email, customer_id, plan, session):
    """
    Called when a subscription is confirmed. Provision the account here:
    - plan == "standard"     → FinReportAI-branded reports
    - plan == "white_label"  → fully white-labelled reports
    """
    app.logger.info("New subscription: email=%s plan=%s customer=%s", email, plan, customer_id)
    # TODO: create user record, send welcome email, set plan flags, etc.


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)))
