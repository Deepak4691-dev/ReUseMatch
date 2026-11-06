"""Image -> category suggestion.

Uses a pretrained MobileNetV2 (ImageNet) if TensorFlow is installed, mapping its labels to
our categories. Without TensorFlow it falls back to filename keywords, so the app always runs.
The donor always confirms or corrects the suggestion; corrections are stored for later fine-tuning.
"""
import io

LABEL_MAP = {
    "furniture": ["desk", "chair", "couch", "table", "wardrobe", "bookcase", "chiffonier", "cradle",
                  "crib", "bed", "dresser", "stool", "bench", "sofa", "cabinet", "file", "throne", "four-poster"],
    "electronics": ["laptop", "notebook", "computer", "monitor", "screen", "keyboard", "mouse", "phone",
                    "television", "printer", "projector", "radio", "speaker", "modem", "remote", "iPod", "hard_disc", "fan", "microwave"],
    "books": ["book", "binder", "comic", "bookshop", "envelope", "menu", "web_site"],
    "materials": ["plank", "brick", "pipe", "wood", "tile", "roll", "barrel", "crate", "bucket", "ladder", "lumber", "wire", "plywood"],
}
FILENAME_HINTS = {
    "furniture": ["chair", "table", "desk", "sofa", "bed", "shelf", "cupboard", "almirah", "bench"],
    "electronics": ["laptop", "phone", "monitor", "keyboard", "mouse", "tv", "printer", "fan", "charger", "cpu"],
    "books": ["book", "notes", "novel", "textbook"],
    "materials": ["wood", "plank", "pipe", "tile", "brick", "metal", "cloth"],
}

_model = None
_tf_failed = False


def _load():
    global _model, _tf_failed
    if _model is not None or _tf_failed:
        return _model
    try:
        from tensorflow.keras.applications import MobileNetV2
        _model = MobileNetV2(weights="imagenet")
    except Exception:
        _tf_failed = True
    return _model


def _by_filename(filename):
    name = (filename or "").lower()
    for cat, words in FILENAME_HINTS.items():
        if any(w in name for w in words):
            return {"category": cat, "confidence": 0.5, "label": name, "method": "filename"}
    return {"category": "other", "confidence": 0.0, "label": "", "method": "none"}


def classify_image(data: bytes, filename: str = ""):
    model = _load()
    if model is None:
        return _by_filename(filename)
    try:
        import numpy as np
        from PIL import Image
        from tensorflow.keras.applications.mobilenet_v2 import decode_predictions, preprocess_input
        img = Image.open(io.BytesIO(data)).convert("RGB").resize((224, 224))
        preds = model.predict(preprocess_input(np.array(img, dtype="float32")[None]), verbose=0)
        top = decode_predictions(preds, top=5)[0]
    except Exception:
        return _by_filename(filename)

    totals = {c: 0.0 for c in LABEL_MAP}
    for _, label, prob in top:
        for cat, words in LABEL_MAP.items():
            if any(w.lower() in label.lower() for w in words):
                totals[cat] += float(prob)
    best = max(totals, key=totals.get)
    if totals[best] < 0.08:
        res = _by_filename(filename)
        res["label"] = top[0][1]
        return res
    return {"category": best, "confidence": round(min(totals[best], 1.0), 2), "label": top[0][1], "method": "mobilenetv2"}
