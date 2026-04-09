const statusEl = document.querySelector("#status");
const summaryEl = document.querySelector("#summary");
const fieldsEl = document.querySelector("#fields");
const redactionForm = document.querySelector("#redaction-form");
const outputEl = document.querySelector("#output");
const historyEl = document.querySelector("#history");
const contextEl = document.querySelector("#context");

let currentScan = null;

function setStatus(message, kind = "") {
  statusEl.className = `status ${kind}`;
  statusEl.textContent = message;
}

function renderSummary(scan) {
  summaryEl.innerHTML = `
    <div class="metric"><span>Document type</span><strong>${scan.document_type}</strong></div>
    <div class="metric"><span>Confidence</span><strong>${Number(scan.confidence ?? 0).toFixed(2)}</strong></div>
    <div class="metric"><span>PEI before</span><strong>${Number(scan.pei_before ?? 0).toFixed(1)}</strong></div>
  `;
}

function renderFields(fields) {
  if (!fields.length) {
    fieldsEl.innerHTML = "<p>No PII fields were detected.</p>";
    redactionForm.hidden = true;
    return;
  }
  fieldsEl.innerHTML = fields
    .map((field) => {
      const safeName = field.field_name.replace(/[^a-zA-Z0-9_-]/g, "_");
      return `
        <div class="field-row">
          <div>
            <strong>${field.field_name}</strong>
            <p>${field.explanation || "Sensitive field detected."}</p>
            <p>Required: ${field.required ? "yes" : "no"} · Weight: ${field.sensitivity_weight} · Confidence: ${Number(field.confidence).toFixed(2)}</p>
          </div>
          <label>
            Decision
            <select name="${safeName}" data-field-name="${field.field_name}">
              <option value="redact" ${field.redaction_decision === "redact" ? "selected" : ""}>Redact</option>
              <option value="mask" ${field.redaction_decision === "mask" ? "selected" : ""}>Mask</option>
              <option value="allow" ${field.redaction_decision === "allow" ? "selected" : ""}>Allow</option>
            </select>
          </label>
        </div>
      `;
    })
    .join("");
  redactionForm.hidden = false;
}

function renderScan(scan) {
  currentScan = scan;
  renderSummary(scan);
  renderFields(scan.detected_fields || []);
  if (scan.highlighted_text) {
    outputEl.innerHTML = `<strong>Highlighted text</strong><p>${scan.highlighted_text}</p>`;
  } else {
    outputEl.innerHTML = "";
  }
}

async function apiFetch(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

document.querySelector("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.querySelector("#document-file");
  if (!fileInput.files.length) {
    setStatus("Choose a document file first.", "warning");
    return;
  }
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("context", contextEl.value);
  setStatus("Scanning document...");
  event.submitter.disabled = true;
  try {
    const scan = await apiFetch("/upload", { method: "POST", body: formData });
    setStatus("Scan complete.");
    renderScan(scan);
    loadHistory();
  } catch (error) {
    setStatus(error.message, "danger");
  } finally {
    event.submitter.disabled = false;
  }
});

document.querySelector("#text-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = document.querySelector("#raw-text").value.trim();
  if (!text) {
    setStatus("Paste text before scanning.", "warning");
    return;
  }
  setStatus("Scanning text...");
  event.submitter.disabled = true;
  try {
    const scan = await apiFetch("/scan-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, context: contextEl.value }),
    });
    setStatus("Text scan complete.");
    renderScan(scan);
    loadHistory();
  } catch (error) {
    setStatus(error.message, "danger");
  } finally {
    event.submitter.disabled = false;
  }
});

redactionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentScan) return;
  const decisions = {};
  redactionForm.querySelectorAll("select[data-field-name]").forEach((select) => {
    decisions[select.dataset.fieldName] = select.value;
  });
  setStatus("Applying redactions...");
  event.submitter.disabled = true;
  try {
    const result = await apiFetch("/redact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scan_id: currentScan.scan_id, redaction_decisions: decisions }),
    });
    setStatus(`Redaction complete. PEI after: ${Number(result.pei_after).toFixed(1)}`);
    outputEl.innerHTML = `
      <strong>Redacted document</strong>
      <img src="${result.redacted_image_url}" alt="Redacted document output" />
      <p>Audit report is available at <a href="/audit/${currentScan.scan_id}" target="_blank" rel="noreferrer">/audit/${currentScan.scan_id}</a>.</p>
    `;
    loadHistory();
  } catch (error) {
    setStatus(error.message, "danger");
  } finally {
    event.submitter.disabled = false;
  }
});

async function loadHistory() {
  try {
    const scans = await apiFetch("/scans");
    historyEl.innerHTML = scans.length
      ? scans
          .map(
            (scan) => `
              <div class="history-row">
                <div><strong>${scan.filename}</strong><br /><span>${scan.document_type} · ${new Date(scan.timestamp).toLocaleString()}</span></div>
                <div><strong>${Number(scan.pei_before).toFixed(1)}</strong><span> PEI</span></div>
              </div>
            `,
          )
          .join("")
      : "<p>No previous scans.</p>";
  } catch {
    historyEl.innerHTML = "<p>Scan history is unavailable.</p>";
  }
}

loadHistory();
