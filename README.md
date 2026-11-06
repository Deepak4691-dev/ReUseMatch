# ReUseMatch AI

Before throwing something away, find out whether somebody else can use it.

A Flask web app where donors list unwanted items (with an AI category suggestion from a photo),
recipients post needs, an explainable score matches the two, pickups are scheduled, and an
impact dashboard tracks kilograms diverted from landfill and estimated CO2 avoided (SDG 12, 11, 13).

## Run it

```bash
python -m venv venv
venv\Scripts\activate          # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
python seed.py                 # demo data (optional)
python app.py                  # http://127.0.0.1:5000
```

Demo logins (after `python seed.py`):

| Role | Email | Password |
|---|---|---|
| Admin | admin@reusematch.local | admin123 |
| Donor | aarav@example.com | demo123 |
| Recipient (NGO) | hope@example.com | demo123 |

Delete `reusematch.db` and run `seed.py` again to reset.

## Optional: real image classification

`pip install tensorflow` enables MobileNetV2 (ImageNet weights, downloaded on first use).
Its labels are mapped to the app's categories in `classifier.py`. Without TensorFlow the app
falls back to filename keywords, so everything else still works. The donor always confirms the
category, and the AI suggestion is stored next to the final choice so you can measure accuracy
(shown on the Admin page) and later fine-tune on the corrections.

## Restrict sign-up to college emails

```bash
set ALLOWED_EMAIL_DOMAIN=cumail.in      # Windows   (macOS/Linux: export ...)
```

## How it works

| File | Purpose |
|---|---|
| `app.py` | Routes: auth, listings, requests and scheduling, needs, dashboard, map API, impact, admin |
| `matching.py` | `score = 0.35 category + 0.25 distance + 0.15 urgency + 0.10 condition + 0.15 keyword similarity` |
| `classifier.py` | Photo -> category suggestion (MobileNetV2 or filename fallback) |
| `config.py` | Weights, categories, default location, weight and CO2 assumptions |
| `schema.sql` | Tables: users, items, requests, needs |
| `seed.py` | Demo users, items and needs |

Matching weights and every impact assumption live in `config.py`; state them in your report.
Distance uses the haversine formula on stored latitude and longitude.

## Item life cycle

`available` -> donor accepts a request and confirms a time -> `reserved` -> donor marks collected -> `collected`
(counts toward the impact dashboard). Cancelling an accepted request returns the item to `available`.

## Known limitations (good "future work" for the report)

- No CSRF protection or email verification; add Flask-WTF and email confirmation before deploying publicly.
- Condition is declared by the donor; the AI only suggests the category.
- Maps and charts load Leaflet, OpenStreetMap and Chart.js from the internet.
- Impact numbers are estimates based on average weights and illustrative emission factors.
- Quantity is not split across requests (one accepted request reserves the whole listing).
