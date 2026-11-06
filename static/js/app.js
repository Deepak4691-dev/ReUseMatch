// Fill a lat/lng pair from the browser's location.
function useMyLocation(latId, lngId, statusId) {
  const status = document.getElementById(statusId);
  if (!navigator.geolocation) { status.textContent = "Location is not supported in this browser."; return; }
  status.textContent = "Finding your location...";
  navigator.geolocation.getCurrentPosition(
    p => {
      document.getElementById(latId).value = p.coords.latitude.toFixed(6);
      document.getElementById(lngId).value = p.coords.longitude.toFixed(6);
      status.textContent = "Location set.";
    },
    () => { status.textContent = "Could not read your location. Enter coordinates manually or keep the default."; }
  );
}

// Ask the server to suggest a category from the uploaded photo.
function setupClassifier() {
  const input = document.getElementById("image");
  if (!input) return;
  input.addEventListener("change", async () => {
    const box = document.getElementById("ai-box");
    if (!input.files.length) return;
    box.textContent = "Analysing photo...";
    const fd = new FormData();
    fd.append("image", input.files[0]);
    try {
      const res = await fetch("/api/classify", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) { box.textContent = data.error || "Could not analyse the photo."; return; }
      document.getElementById("ai_category").value = data.category;
      document.getElementById("ai_confidence").value = data.confidence;
      if (data.method === "none") {
        box.textContent = "No suggestion for this photo. Choose the category yourself.";
      } else {
        document.getElementById("category").value = data.category;
        box.textContent = `Suggested category: ${data.category} (${Math.round(data.confidence * 100)}% confidence, ${data.method}). Change it if it is wrong.`;
      }
    } catch (e) { box.textContent = "Could not reach the classifier. Choose the category yourself."; }
  });
}
document.addEventListener("DOMContentLoaded", setupClassifier);
