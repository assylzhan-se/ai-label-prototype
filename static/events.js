// Client-side event logging: viewing time per profile, like/skip, label interaction.
(function () {
  const S = window.STUDY;
  const queue = [];
  const t0 = performance.now();
  const push = (type, extra) => queue.push(Object.assign({type, profile_id: S.profile, ts: Date.now()}, extra || {}));
  const flush = (beacon) => {
    if (!queue.length) return;
    const body = JSON.stringify({study_code: S.code, events: queue.splice(0)});
    if (beacon && navigator.sendBeacon) {
      navigator.sendBeacon("/api/events", new Blob([body], {type: "application/json"}));
    } else {
      fetch("/api/events", {method: "POST", headers: {"Content-Type": "application/json"}, body});
    }
  };
  push("view_start");
  document.querySelectorAll("[data-ev]").forEach(el =>
    el.addEventListener("change", () => push(el.dataset.ev)));
  document.querySelectorAll(".origin-label").forEach(label => {
    label.addEventListener("mouseenter", () => push("label_hover"));
    label.addEventListener("click", () => push("label_click"));
  });
  document.getElementById("rating-form").addEventListener("submit", () => {
    push("view_end", {value_ms: Math.round(performance.now() - t0)});
    flush(true);
  });
  setInterval(() => flush(false), 5000);
})();

// v4: enable the Next button only after the minimum viewing time (also enforced on the server)
(function () {
  const btn = document.getElementById("next-btn");
  if (!btn) return;
  let left = parseInt(btn.dataset.min || "0", 10);
  const note = document.getElementById("wait-note");
  if (left <= 0) return;
  btn.disabled = true;
  const tick = () => {
    if (left <= 0) { btn.disabled = false; note.textContent = ""; return; }
    note.textContent = "  Please look at the profile (" + left + " s)";
    left -= 1; setTimeout(tick, 1000);
  };
  tick();
})();
