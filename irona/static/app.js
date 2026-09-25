"use strict";
const byId = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="irona-token"]').content;
const input = byId("message");
let state = null;
let connected = false;
let pending = false;
let messageSignature = "";
let clientError = "";
const phases = {idle: "Ready", generating: "Generating reply", synthesizing: "Synthesizing speech", speaking: "Speaking", stopping: "Stopping audio", error: "Needs attention"};

function controls() {
  byId("send").disabled = !connected || pending || Boolean(state?.busy) || !input.value.trim();
  byId("reset").disabled = !connected || pending || Boolean(state?.busy) || !state?.messages.length;
  byId("stop").disabled = !connected || pending || state?.phase !== "speaking";
  byId("count").textContent = `${input.value.length} / 2,000`;
}

function render(next) {
  state = next;
  byId("connection-label").textContent = "Connected";
  byId("connection-dot").classList.add("online");
  byId("phase").textContent = phases[state.phase] || state.phase;
  byId("model").textContent = state.config.model;
  byId("voice").textContent = state.config.voice;
  byId("tts-model").textContent = state.config.tts_model;
  const onTemi = state.config.audio_output === "temi";
  byId("destination").textContent = onTemi ? "Temi speakers" : "Ubuntu desktop";
  byId("output-detail").textContent = onTemi ? "ADB development connection" : "Development output";
  byId("sink").textContent = onTemi ? "Irona player" : state.config.audio_sink;
  byId("turns").textContent = `${state.turns} spoken turn${state.turns === 1 ? "" : "s"}`;
  byId("playback-label").textContent = state.phase === "speaking" ? (onTemi ? "Playing on Temi" : "Playing on Ubuntu") : state.phase === "stopping" ? "Stopping" : "Silent";
  document.body.classList.toggle("speaking", state.phase === "speaking");
  byId("timing").textContent = !state.busy && state.timings.total != null ? `${state.timings.total.toFixed(1)} s` : "";
  const error = clientError || state.error || (!state.config.key_ready ? "ElevenLabs key is missing. Set it in Ubuntu's .env and restart Irona." : "");
  byId("error").textContent = error;
  byId("error").hidden = !error;
  const signature = JSON.stringify(state.messages);
  if (signature !== messageSignature) {
    const transcript = byId("transcript");
    const nearBottom = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 80;
    const previousCount = transcript.querySelectorAll(".message").length;
    transcript.replaceChildren();
    if (!state.messages.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      const icon = document.createElement("img");
      icon.src = "/static/icons/audio-lines.svg";
      icon.alt = "";
      icon.width = 40;
      icon.height = 40;
      const text = document.createElement("p");
      text.textContent = "Ready";
      empty.append(icon, text);
      transcript.append(empty);
    }
    for (const message of state.messages) {
      const article = document.createElement("article");
      article.className = `message ${message.role}`;
      const label = document.createElement("div");
      label.className = "speaker";
      label.textContent = message.role === "user" ? "You" : "Irona";
      const text = document.createElement("p");
      text.textContent = message.text;
      article.append(label, text);
      if (message.role === "assistant") {
        const delivery = document.createElement("span");
        delivery.className = `delivery ${message.delivery}`;
        delivery.textContent = {pending: "Preparing speech", speaking: "Speaking", spoken: "Spoken", stopped: "Audio stopped", failed: "Audio unavailable"}[message.delivery] || "";
        article.append(delivery);
      }
      transcript.append(article);
    }
    if (nearBottom || state.messages.length > previousCount) transcript.scrollTop = transcript.scrollHeight;
    messageSignature = signature;
  }
  controls();
}

async function command(path, body = {}) {
  if (pending) return;
  pending = true;
  clientError = "";
  controls();
  try {
    const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json", "X-Irona-Token": token}, body: JSON.stringify(body), signal: AbortSignal.timeout(5000)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Command failed.");
    connected = true;
    if (path === "/api/turn") input.value = "";
    render(data);
  } catch (error) {
    clientError = error.name === "TimeoutError" ? "Connection timed out. Check the turn status before sending again." : error.message;
    byId("error").textContent = clientError;
    byId("error").hidden = false;
  } finally {
    pending = false;
    controls();
    input.focus();
  }
}

async function poll() {
  try {
    const response = await fetch("/api/state", {cache: "no-store", signal: AbortSignal.timeout(4000)});
    if (!response.ok) throw new Error("Disconnected");
    connected = true;
    render(await response.json());
  } catch (_) {
    connected = false;
    byId("connection-label").textContent = "Disconnected";
    byId("connection-dot").classList.remove("online");
    byId("phase").textContent = "Waiting for connection";
    document.body.classList.remove("speaking");
    controls();
  } finally {
    setTimeout(poll, connected ? 350 : 1500);
  }
}

byId("composer").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!byId("send").disabled) command("/api/turn", {message: input.value});
});
input.addEventListener("input", controls);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    byId("composer").requestSubmit();
  }
});
byId("reset").addEventListener("click", () => command("/api/reset"));
byId("stop").addEventListener("click", () => command("/api/stop"));
poll();
