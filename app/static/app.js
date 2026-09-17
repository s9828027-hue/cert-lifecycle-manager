const STATUS_LABEL = {
  active: "正常",
  expiring_soon: "即將到期",
  expired: "已逾期",
  renewing: "更換中",
};

const EVENT_LABEL = {
  expiry_warning: "⚠️ 到期預警",
  renewal_started: "🔄 開始更換",
  renewal_success: "✅ 更換成功",
  renewal_failed: "❌ 更換失敗",
};

function daysLeftClass(days) {
  if (days < 0) return "bad";
  if (days <= 7) return "warn";
  return "ok";
}

function fmtDate(iso) {
  return iso.slice(0, 10);
}

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function renderStats(certs) {
  const counts = { total: certs.length, active: 0, expiring_soon: 0, expired: 0 };
  for (const c of certs) counts[c.status] = (counts[c.status] || 0) + 1;
  document.querySelectorAll("#stats .stat-card").forEach((card) => {
    const key = card.dataset.key;
    card.querySelector(".stat-value").textContent = counts[key] ?? 0;
  });
}

function buildRow(cert) {
  const tpl = document.getElementById("row-template");
  const row = tpl.content.cloneNode(true);

  row.querySelector(".device-badge").textContent = cert.device_type;
  row.querySelector(".device-name").textContent = cert.device_name;
  row.querySelector(".domain").textContent = `${cert.domain} (${cert.cert_type})`;
  row.querySelector(".expires").textContent = fmtDate(cert.expires_at);

  const daysEl = row.querySelector(".days-left");
  daysEl.textContent = cert.days_left < 0 ? `逾期 ${-cert.days_left} 天` : `${cert.days_left} 天`;
  daysEl.classList.add(daysLeftClass(cert.days_left));

  const statusEl = row.querySelector(".status-badge");
  statusEl.textContent = STATUS_LABEL[cert.status] || cert.status;
  statusEl.classList.add(cert.status);

  const tr = row.querySelector("tr");
  tr.dataset.certId = cert.id;

  const simulateBtn = row.querySelector(".btn-simulate");
  simulateBtn.addEventListener("click", async () => {
    simulateBtn.disabled = true;
    try {
      await fetchJSON(`/api/certificates/${cert.id}/simulate-expiry?days=5`, { method: "POST" });
      await refresh();
    } catch (e) {
      alert("操作失敗：" + e.message);
    } finally {
      simulateBtn.disabled = false;
    }
  });

  const certInput = row.querySelector(".cert-input");
  const keyInput = row.querySelector(".key-input");
  const uploadBtn = row.querySelector(".btn-upload");

  function refreshUploadState() {
    uploadBtn.disabled = !(certInput.files.length && keyInput.files.length);
  }
  certInput.addEventListener("change", () => {
    certInput.closest(".upload-label").classList.toggle("has-file", certInput.files.length > 0);
    refreshUploadState();
  });
  keyInput.addEventListener("change", () => {
    keyInput.closest(".upload-label").classList.toggle("has-file", keyInput.files.length > 0);
    refreshUploadState();
  });

  uploadBtn.addEventListener("click", async () => {
    uploadBtn.disabled = true;
    uploadBtn.textContent = "上傳中…";
    const form = new FormData();
    form.append("cert_file", certInput.files[0]);
    form.append("key_file", keyInput.files[0]);
    try {
      await fetchJSON(`/api/certificates/${cert.id}/upload`, { method: "POST", body: form });
      await refresh();
    } catch (e) {
      alert("更換失敗：" + e.message);
    } finally {
      uploadBtn.textContent = "上傳並更換";
      refreshUploadState();
    }
  });

  return row;
}

function renderEvents(events) {
  const feed = document.getElementById("event-feed");
  feed.innerHTML = "";
  if (events.length === 0) {
    feed.innerHTML = '<li class="loading">尚無事件</li>';
    return;
  }
  for (const ev of events) {
    const li = document.createElement("li");
    li.className = ev.event_type;
    li.innerHTML = `${EVENT_LABEL[ev.event_type] || ev.event_type} &mdash; ${ev.message}
      <span class="event-time">${ev.created_at.replace("T", " ").slice(0, 19)}</span>`;
    feed.appendChild(li);
  }
}

async function refresh() {
  const [certs, events] = await Promise.all([
    fetchJSON("/api/certificates"),
    fetchJSON("/api/events?limit=25"),
  ]);

  renderStats(certs);

  const tbody = document.getElementById("cert-table-body");
  tbody.innerHTML = "";
  if (certs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading">尚無受管理憑證，請先執行 scripts/seed_demo.py</td></tr>';
  } else {
    for (const cert of certs) tbody.appendChild(buildRow(cert));
  }

  renderEvents(events);
}

document.getElementById("scan-now").addEventListener("click", async (e) => {
  e.target.disabled = true;
  e.target.textContent = "掃描中…";
  try {
    await fetchJSON("/api/scan-now", { method: "POST" });
    await refresh();
  } finally {
    e.target.disabled = false;
    e.target.textContent = "立即執行到期掃描";
  }
});

refresh();
setInterval(refresh, 5000);
