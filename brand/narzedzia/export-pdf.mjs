import { spawn } from "node:child_process";
import { tmpdir } from "node:os";
import { writeFileSync, mkdirSync } from "node:fs";
const [,, out, page = "prezentacja.html", shots = ""] = process.argv;
const port = 9337;
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [
  "--headless=new", `--remote-debugging-port=${port}`, "--user-data-dir=" + (process.env.SCRATCH || tmpdir()) + "/mimic-pdf-prof",
  "--window-size=1920,1080", "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws;
for (let i = 0; i < 50; i++) { try { const r = await fetch(`http://127.0.0.1:${port}/json/new?http://127.0.0.1:8765/${page}`, { method: "PUT" }); ws = (await r.json()).webSocketDebuggerUrl; break; } catch { await sleep(200); } }
const sock = new WebSocket(ws);
await new Promise(r => sock.onopen = r);
let idc = 0; const pend = new Map();
sock.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const id = ++idc; pend.set(id, r); sock.send(JSON.stringify({ id, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); return r.result?.result?.value; };
for (let i = 0; i < 100; i++) { if (await ev("document.readyState==='complete'&&window.__ready!==undefined")) break; await sleep(200); }
await ev("window.__ready"); await ev("Promise.all([...document.images].map(i=>i.complete?1:new Promise(r=>i.onload=i.onerror=r)))"); await sleep(500);
if (shots) {
  mkdirSync(shots, { recursive: true });
  await send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  await send("Emulation.setEmulatedMedia", { media: "print" });
  const n = await ev("document.querySelectorAll('.slide').length");
  for (let i = 0; i < n; i++) {
    const y = await ev(`document.querySelectorAll('.slide')[${i}].getBoundingClientRect().top+scrollY`);
    const r = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y, width: 1920, height: 1080, scale: 0.5 }, captureBeyondViewport: true });
    writeFileSync(`${shots}/${String(i + 1).padStart(2, "0")}.png`, Buffer.from(r.result.data, "base64"));
  }
  await send("Emulation.setEmulatedMedia", { media: "" });
}
const pdf = await send("Page.printToPDF", { printBackground: true, preferCSSPageSize: true, marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0 });
const buf = Buffer.from(pdf.result.data, "base64");
writeFileSync(out, buf);
console.log("ok", (buf.length / 1e6).toFixed(2) + "MB");
sock.close(); chrome.kill(); process.exit(0);
