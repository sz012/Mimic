import { spawn } from "node:child_process";
import { tmpdir } from "node:os";
import { writeFileSync, mkdirSync } from "node:fs";
const outDir = process.argv[2] || "materialy";
const port = 9334;
mkdirSync(outDir, { recursive: true });
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [
  "--headless=new", `--remote-debugging-port=${port}`, "--user-data-dir=" + (process.env.SCRATCH || tmpdir()) + "/mimic-chrome-png",
  "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws;
for (let i = 0; i < 50; i++) { try { const r = await fetch(`http://127.0.0.1:${port}/json/new?http://127.0.0.1:8765/materialy.html`, { method: "PUT" }); ws = (await r.json()).webSocketDebuggerUrl; break; } catch { await sleep(200); } }
const sock = new WebSocket(ws);
await new Promise(r => sock.onopen = r);
let idc = 0; const pend = new Map();
sock.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const id = ++idc; pend.set(id, r); sock.send(JSON.stringify({ id, method, params })); });
const ev = async expr => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails)); return r.result.result.value; };
for (let i = 0; i < 100; i++) { if (await ev("!!window.__ready")) break; await sleep(200); }
for (const n of await ev("__names()")) { writeFileSync(`${outDir}/${n}.png`, Buffer.from(await ev(`__png(${JSON.stringify(n)})`), "base64")); console.log(n); }
sock.close(); chrome.kill(); process.exit(0);
