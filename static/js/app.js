const config = window.APP_CONFIG;

const elements = {
  uploadForm: document.getElementById("uploadForm"),
  dropZone: document.getElementById("dropZone"),
  videoInput: document.getElementById("videoInput"),
  fileMeta: document.getElementById("fileMeta"),
  processButton: document.getElementById("processButton"),
  uploadPercent: document.getElementById("uploadPercent"),
  processPercent: document.getElementById("processPercent"),
  uploadProgressText: document.getElementById("uploadProgressText"),
  processProgressText: document.getElementById("processProgressText"),
  uploadProgressBar: document.getElementById("uploadProgressBar"),
  processProgressBar: document.getElementById("processProgressBar"),
  jobStatus: document.getElementById("jobStatus"),
  statusHeading: document.getElementById("statusHeading"),
  statusMessage: document.getElementById("statusMessage"),
  resultBadge: document.getElementById("resultBadge"),
  videoPreview: document.getElementById("videoPreview"),
  countsList: document.getElementById("countsList"),
  totalObjects: document.getElementById("totalObjects"),
};

let selectedFile = null;
let pollTimer = null;

function initialize() {
  bindEvents();
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function bindEvents() {
  elements.videoInput.addEventListener("change", () => setSelectedFile(elements.videoInput.files[0]));
  elements.uploadForm.addEventListener("submit", handleUpload);

  ["dragenter", "dragover"].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.add("dragging");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.remove("dragging");
    });
  });

  elements.dropZone.addEventListener("drop", (event) => {
    const file = event.dataTransfer.files[0];
    setSelectedFile(file);
  });
}

function setSelectedFile(file) {
  if (!file) {
    selectedFile = null;
    elements.fileMeta.textContent = "";
    return;
  }

  const validationError = validateFile(file);
  if (validationError) {
    selectedFile = null;
    elements.videoInput.value = "";
    elements.fileMeta.textContent = validationError;
    setStatus("Invalid file", validationError, "Failed");
    return;
  }

  selectedFile = file;
  elements.fileMeta.textContent = `${file.name} - ${formatBytes(file.size)}`;
  setStatus("Ready to process", "Click Process Video to start.", "Ready");
}

function validateFile(file) {
  const extension = file.name.split(".").pop().toLowerCase();
  if (!config.allowedExtensions.includes(extension)) {
    return "Unsupported format. Use MP4, AVI, MOV, or MKV.";
  }

  const maxBytes = config.maxFileSizeMb * 1024 * 1024;
  if (file.size > maxBytes) {
    return `File is too large. Maximum size is ${config.maxFileSizeMb} MB.`;
  }

  return "";
}

function handleUpload(event) {
  event.preventDefault();
  if (!selectedFile) {
    setStatus("Choose a video", "Drop or browse for a supported video before processing.", "Waiting");
    return;
  }

  clearInterval(pollTimer);
  resetResultPreview();
  setProgress("upload", 0, "Starting");
  setProgress("process", 0, "Queued");
  setStatus("Uploading video", "Sending the file to the Flask backend.", "Uploading");
  elements.processButton.disabled = true;

  const formData = new FormData();
  formData.append("video", selectedFile);

  const request = new XMLHttpRequest();
  request.open("POST", "/api/upload");

  request.upload.addEventListener("progress", (event) => {
    if (!event.lengthComputable) {
      return;
    }
    const percent = Math.round((event.loaded / event.total) * 100);
    setProgress("upload", percent, `${percent}%`);
  });

  request.addEventListener("load", () => {
    let response = {};
    try {
      response = JSON.parse(request.responseText || "{}");
    } catch (_error) {
      response = {};
    }

    if (request.status >= 400) {
      const message = response.error || "Upload failed.";
      setStatus("Upload failed", message, "Failed");
      elements.processButton.disabled = false;
      return;
    }

    setProgress("upload", 100, "Complete");
    setStatus("Processing video", response.message || "Analyzing frames.", "Processing");
    pollJob(response.job_id);
  });

  request.addEventListener("error", () => {
    setStatus("Upload failed", "The browser could not reach the backend.", "Failed");
    elements.processButton.disabled = false;
  });

  request.send(formData);
}

function pollJob(jobId) {
  const fetchStatus = async () => {
    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Could not fetch job status.");
      }
      renderJob(payload);
      if (payload.status === "completed" || payload.status === "failed") {
        clearInterval(pollTimer);
        elements.processButton.disabled = false;
      }
    } catch (error) {
      clearInterval(pollTimer);
      setStatus("Status unavailable", error.message, "Failed");
      elements.processButton.disabled = false;
    }
  };

  fetchStatus();
  pollTimer = setInterval(fetchStatus, 1400);
}

function renderJob(payload) {
  const progress = Number(payload.progress || 0);
  setProgress("process", progress, `${progress}%`);
  setStatus(statusTitle(payload.status), payload.message || "Processing", statusLabel(payload.status));
  elements.resultBadge.textContent = statusLabel(payload.status);

  if (payload.result) {
    renderResult(payload.result, payload.status === "completed");
  }

  if (payload.status === "completed") {
    playProcessedVideo(payload.processed_video_url);
    setStatus("Processing complete", "Annotated video preview is ready.", "Complete");
  }

  if (payload.status === "failed") {
    setStatus("Processing failed", payload.error || "The detection job did not complete.", "Failed");
  }
}

function renderResult(result, isFinal) {
  const counts = result.counts || {};
  const total = Number(result.total_unique_objects || 0);

  elements.totalObjects.textContent = total.toLocaleString();
  renderCounts(counts);
}

function renderCounts(counts) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    elements.countsList.innerHTML = `<p class="text-sm text-slate-500">No tracked objects confirmed yet.</p>`;
    return;
  }

  elements.countsList.innerHTML = entries
    .map(([category, count]) => `
      <div class="count-row">
        <span title="${escapeHtml(titleCase(category))}">${pluralize(titleCase(category), count)}</span>
        <strong>${Number(count).toLocaleString()}</strong>
      </div>
    `)
    .join("");
}

function setStatus(heading, message, status) {
  elements.statusHeading.textContent = heading;
  elements.statusMessage.textContent = message;
  elements.jobStatus.textContent = status;
}

function setProgress(type, percent, text) {
  const clamped = Math.max(0, Math.min(100, Number(percent || 0)));
  if (type === "upload") {
    elements.uploadPercent.textContent = `${clamped}%`;
    elements.uploadProgressText.textContent = text;
    elements.uploadProgressBar.style.width = `${clamped}%`;
  } else {
    elements.processPercent.textContent = `${clamped}%`;
    elements.processProgressText.textContent = text;
    elements.processProgressBar.style.width = `${clamped}%`;
  }
}

function resetResultPreview() {
  elements.videoPreview.pause();
  elements.videoPreview.removeAttribute("src");
  elements.videoPreview.load();
  elements.resultBadge.textContent = "Processing";
}

function playProcessedVideo(videoUrl) {
  if (!videoUrl) {
    return;
  }

  const separator = videoUrl.includes("?") ? "&" : "?";
  elements.videoPreview.src = `${videoUrl}${separator}v=${Date.now()}`;
  elements.videoPreview.muted = true;
  elements.videoPreview.load();

  const startPlayback = () => {
    elements.videoPreview.removeEventListener("canplay", startPlayback);
    elements.videoPreview.play().catch(() => {
      setStatus("Preview ready", "Press play on the annotated video preview.", "Complete");
    });
  };

  elements.videoPreview.addEventListener("canplay", startPlayback);
  elements.videoPreview.addEventListener("error", () => {
    setStatus("Preview ready", "The video was processed. Use the video controls to retry playback.", "Complete");
  }, { once: true });
}

function statusTitle(status) {
  const titles = {
    queued: "Queued",
    processing: "Processing video",
    completed: "Processing complete",
    failed: "Processing failed",
  };
  return titles[status] || "Working";
}

function statusLabel(status) {
  const labels = {
    queued: "Queued",
    processing: "Processing",
    completed: "Complete",
    failed: "Failed",
  };
  return labels[status] || "Working";
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatDuration(seconds) {
  const value = Math.max(0, Math.round(Number(seconds || 0)));
  const minutes = Math.floor(value / 60);
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  const remainingSeconds = value % 60;
  if (hours) return `${hours}h ${remainingMinutes}m ${remainingSeconds}s`;
  if (minutes) return `${minutes}m ${remainingSeconds}s`;
  return `${remainingSeconds}s`;
}

function titleCase(value) {
  return String(value || "")
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function pluralize(label, count) {
  if (Number(count) === 1) {
    return label;
  }
  if (label.endsWith("s")) {
    return label;
  }
  return `${label}s`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.addEventListener("DOMContentLoaded", initialize);
