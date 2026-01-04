import express from "express";

const router = express.Router();

/**
 * CONFIG
 */
const PAYPAL_MODE = process.env.PAYPAL_MODE || "sandbox";
const PAYPAL_BASE =
  PAYPAL_MODE === "live" ? "https://api-m.paypal.com" : "https://api-m.sandbox.paypal.com";

const PUBLIC_BASE_URL = process.env.PUBLIC_BASE_URL || "https://ecu-forgex-cloud.onrender.com";
const PAYPAL_CLIENT_ID = process.env.PAYPAL_CLIENT_ID;
const PAYPAL_CLIENT_SECRET = process.env.PAYPAL_CLIENT_SECRET;

/**
 * Tiny in-memory store (V1)
 * (después lo pasamos a DB real)
 */
const store = {
  orders: new Map(), // order_id -> order
};

function uid(prefix = "ORD") {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`.toUpperCase();
}

function priceByPatch(p) {
  const PR = {
    REV_LIMITER: 49,
    DPF_OFF: 99,
    EGR_OFF: 79,
    CAT_OFF: 79,
    ADBLUE_OFF: 89,
    TOP_SPEED_OFF: 49,
    DTC_OFF: 39,
  };
  return PR[p] ?? 0;
}

function calcTotalUSD(patches = []) {
  return patches.reduce((s, p) => s + priceByPatch(p), 0);
}

async function paypalAccessToken() {
  if (!PAYPAL_CLIENT_ID || !PAYPAL_CLIENT_SECRET) {
    throw new Error("Missing PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET");
  }

  const auth = Buffer.from(`${PAYPAL_CLIENT_ID}:${PAYPAL_CLIENT_SECRET}`).toString("base64");

  const r = await fetch(`${PAYPAL_BASE}/v1/oauth2/token`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });

  if (!r.ok) {
    const t = await r.text().catch(() => "");
    throw new Error(`PayPal token failed (${r.status}): ${t || "no-body"}`);
  }

  const j = await r.json();
  return j.access_token;
}

async function paypalCreateOrder({ totalUSD, returnUrl, cancelUrl, description }) {
  const token = await paypalAccessToken();

  const payload = {
    intent: "CAPTURE",
    purchase_units: [
      {
        description: description || "ECU FORGE X services",
        amount: { currency_code: "USD", value: totalUSD.toFixed(2) },
      },
    ],
    application_context: {
      return_url: returnUrl,
      cancel_url: cancelUrl,
      user_action: "PAY_NOW",
      brand_name: "ECU FORGE X",
      shipping_preference: "NO_SHIPPING",
    },
  };

  const r = await fetch(`${PAYPAL_BASE}/v2/checkout/orders`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!r.ok) {
    const t = await r.text().catch(() => "");
    throw new Error(`PayPal create order failed (${r.status}): ${t || "no-body"}`);
  }

  const j = await r.json();
  const approve = (j.links || []).find((l) => l.rel === "approve")?.href;
  return { paypal_order_id: j.id, approve_url: approve };
}

/**
 * POST /public/checkout
 * body: { customer, vehicle, patches }
 * resp: { order_id, checkout_url }
 */
router.post("/public/checkout", async (req, res) => {
  try {
    const { customer, vehicle, patches } = req.body || {};

    if (!customer?.email || !customer?.name) {
      return res.status(400).json({ error: "Missing customer (name, email)" });
    }

    const patchList = Array.isArray(patches) ? patches : [];
    if (!patchList.length) {
      return res.status(400).json({ error: "No patches selected" });
    }

    const totalUSD = calcTotalUSD(patchList);
    if (totalUSD <= 0) {
      return res.status(400).json({ error: "Invalid total" });
    }

    const order_id = uid("ORD");
    const order = {
      id: order_id,
      status: "created",
      paid: false,
      download_ready: false,
      download_url: null,

      total_usd: totalUSD,
      patches: patchList,
      customer,
      vehicle,

      paypal_order_id: null,
      checkout_url: null,

      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    store.orders.set(order_id, order);

    const returnUrl = `${PUBLIC_BASE_URL}/public/paypal/return?order_id=${encodeURIComponent(order_id)}`;
    const cancelUrl = `${PUBLIC_BASE_URL}/static/checkout.html?order_id=${encodeURIComponent(order_id)}&canceled=1`;

    const pp = await paypalCreateOrder({
      totalUSD,
      returnUrl,
      cancelUrl,
      description: `EFX ${patchList.join(", ")} — ${vehicle?.ecu || "ECU"}`,
    });

    order.paypal_order_id = pp.paypal_order_id;
    order.checkout_url = pp.approve_url || null;
    order.updated_at = new Date().toISOString();

    if (!order.checkout_url) {
      return res.status(500).json({ error: "PayPal approve link missing" });
    }

    return res.json({ order_id, checkout_url: order.checkout_url });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e?.message || "Server error" });
  }
});

/**
 * GET /public/order/:id
 */
router.get("/public/order/:id", async (req, res) => {
  const id = req.params.id;
  const o = store.orders.get(id);
  if (!o) return res.status(404).json({ error: "not_found" });

  return res.json({
    id: o.id,
    status: o.status,
    paid: o.paid,
    download_ready: o.download_ready,
    download_url: o.download_url,
    checkout_url: o.checkout_url,
    patches: o.patches,
    total_usd: o.total_usd,
    created_at: o.created_at,
  });
});

/**
 * GET /public/paypal/return
 * PayPal vuelve con ?token=<paypal_order_id>
 */
router.get("/public/paypal/return", async (req, res) => {
  const order_id = String(req.query.order_id || "");
  const token = String(req.query.token || "");
  const o = store.orders.get(order_id);

  if (!o) return res.redirect(`/static/checkout.html?order_id=${encodeURIComponent(order_id)}&err=order_not_found`);
  if (!token) return res.redirect(`/static/checkout.html?order_id=${encodeURIComponent(order_id)}&err=missing_token`);

  o.status = "approved";
  o.paypal_order_id = token;
  o.updated_at = new Date().toISOString();

  return res.redirect(`/static/checkout.html?order_id=${encodeURIComponent(order_id)}&approved=1`);
});

export default router;
