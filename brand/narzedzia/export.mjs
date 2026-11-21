import { spawn } from "node:child_process";
import { tmpdir } from "node:os";
import { writeFileSync } from "node:fs";
const [,, query, out, page = "film.html"] = process.argv;
const port = 9333;
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [
  "--headless=new", `--remote-debugging-port=${port}`, "--user-data-dir=" + (process.env.SCRATCH || tmpdir()) + "/mimic-chrome-prof",
  "--window-size=1920,1080", "--no-first-run", "--disable-background-timer-throttling", "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws;
for (let i = 0; i < 50; i++) { try { const r = await fetch(`http://127.0.0.1:${port}/json/new?http://127.0.0.1:8765/${page}?export%26clean%26${query}`, { method: "PUT" }); const j = await r.json(); ws = j.webSocketDebuggerUrl; break; } catch { await sleep(200); } }
const sock = new WebSocket(ws);
await new Promise(r => sock.onopen = r);
let idc = 0; const pend = new Map();
sock.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const id = ++idc; pend.set(id, r); sock.send(JSON.stringify({ id, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails)); return r.result.result.value; };
for (let i = 0; i < 100; i++) { if (await ev("!!window.__ready")) break; await sleep(200); }
const t0 = Date.now();
const len = await ev(`__exportMp4().then(b=>{window.__mp4=b;return new Promise(res=>{const fr=new FileReader();fr.onload=()=>{window.__b64=fr.result.split(',')[1];res(window.__b64.length)};fr.readAsDataURL(new Blob([b]))})})`);
let b64 = "";
for (let i = 0; i < len; i += 4_000_000) b64 += await ev(`__b64.slice(${i},${i + 4_000_000})`);
writeFileSync(out, Buffer.from(b64, "base64"));
console.log(query, "ok", (Buffer.from(b64, "base64").length / 1e6).toFixed(1) + "MB", ((Date.now() - t0) / 1000).toFixed(0) + "s");
sock.close(); chrome.kill();
process.exit(0);
