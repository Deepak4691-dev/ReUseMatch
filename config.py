"""Central settings and the assumptions used by the impact dashboard."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-before-deploying")
DATABASE = os.path.join(BASE_DIR, "reusematch.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB per upload
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}

# Set e.g. ALLOWED_EMAIL_DOMAIN=cumail.in to restrict sign-up to verified college emails.
ALLOWED_EMAIL_DOMAIN = os.environ.get("ALLOWED_EMAIL_DOMAIN", "")

# Default map centre (Chandigarh University area). Users can override with browser location.
DEFAULT_LAT = 30.7690
DEFAULT_LNG = 76.5750
MAX_DISTANCE_KM = 25.0

CATEGORIES = ["furniture", "electronics", "books", "materials", "other"]
CONDITIONS = ["fair", "good", "like_new"]

# ---- Impact assumptions (state these in your report; they are estimates) ----
UNIT_WEIGHT_KG = {"furniture": 8.0, "electronics": 3.0, "books": 0.5, "materials": 2.0, "other": 1.0}
# Illustrative kg CO2e avoided per kg of item reused instead of replaced with new.
CO2_PER_KG = {"furniture": 1.6, "electronics": 12.0, "books": 1.2, "materials": 0.9, "other": 1.0}

# ---- Matching weights (must sum to 1.0) ----
MATCH_WEIGHTS = {"category": 0.35, "distance": 0.25, "urgency": 0.15, "condition": 0.10, "keywords": 0.15}
