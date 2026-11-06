"""Explainable donor-recipient matching.

score = w1*category + w2*distance + w3*urgency + w4*condition_fit + w5*keyword_similarity
Every component is 0..1, so the breakdown can be shown to users and defended in a viva.
"""
import math
import re

import config

COND_RANK = {"fair": 1, "good": 2, "like_new": 3}
STOP = {"the", "and", "for", "with", "old", "used", "new", "good", "very", "need", "needs", "any", "some"}


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _tokens(text):
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2 and t not in STOP}


def keyword_similarity(a, b):
    """Jaccard overlap of the words in two texts."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def score_pair(item, need, distance_km):
    """Score one item against one need. Returns (score 0-100, breakdown dict)."""
    w = config.MATCH_WEIGHTS
    parts = {
        "category": 1.0 if item["category"] == need["category"] else 0.0,
        "distance": max(0.0, 1.0 - distance_km / config.MAX_DISTANCE_KM),
        "urgency": need["urgency"] / 3.0,
        "condition": 1.0 if COND_RANK[item["condition"]] >= COND_RANK[need["min_condition"]] else 0.3,
        "keywords": keyword_similarity(item["title"] + " " + (item["description"] or ""),
                                       need["title"] + " " + (need["description"] or "")),
    }
    total = sum(w[k] * parts[k] for k in w)
    return round(total * 100), {k: round(v, 2) for k, v in parts.items()}


def match_needs_for_item(item, needs, user_loc):
    """Open needs ranked for one item. user_loc(need) -> (lat, lng) of the recipient."""
    out = []
    for n in needs:
        if n["category"] != item["category"]:
            continue
        lat, lng = user_loc(n)
        d = haversine(item["lat"], item["lng"], lat, lng)
        s, b = score_pair(item, n, d)
        out.append({"need": n, "score": s, "parts": b, "distance": d})
    return sorted(out, key=lambda m: m["score"], reverse=True)


def match_items_for_need(need, items, lat, lng):
    """Available items ranked for one need."""
    out = []
    for it in items:
        if it["category"] != need["category"]:
            continue
        d = haversine(it["lat"], it["lng"], lat, lng)
        s, b = score_pair(it, need, d)
        out.append({"item": it, "score": s, "parts": b, "distance": d})
    return sorted(out, key=lambda m: m["score"], reverse=True)
