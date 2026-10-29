// Captura rutas de la aplicación con Chrome sin interfaz.
//   node scripts/ui/capturar.mjs <light|dark> <carpeta> <ruta>...      (rutas sin «#/»)
// Variables: REVIEWER (identidad del piloto), WIDTH/HEIGHT, CLICK (selector a pulsar
// antes de capturar), WAIT (ms de espera por ruta; 6000 por defecto), SLOW=1 (bloquea el backend para ver estados sin datos),
// CHROME (ruta del navegador), BASE_URL (por defecto http://localhost:5173).
import { spawn } from 'node:child_process'
import { writeFileSync } from 'node:fs'
const CHROME = process.env.CHROME ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = process.env.BASE_URL ?? 'http://localhost:5173'
const [theme, out, ...routes] = process.argv.slice(2)
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--remote-debugging-port=9334', `--user-data-dir=${process.env.TEMP}/shot-chrome`, '--window-size=1440,1000', 'about:blank'])
const wait = (ms) => new Promise(r => setTimeout(r, ms))
let target
for (let i = 0; i < 160 && !target; i++) { await wait(250); try { target = (await (await fetch('http://127.0.0.1:9334/json')).json()).find(t => t.type === 'page') } catch {} }
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise(r => ws.onopen = r)
let n = 0; const pending = new Map()
ws.onmessage = (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d.result); pending.delete(d.id) }
const send = (method, params = {}) => new Promise(r => { const id = ++n; pending.set(id, r); ws.send(JSON.stringify({ id, method, params })) })
await send('Page.enable')
await send('Emulation.setDeviceMetricsOverride', { width: Number(process.env.WIDTH ?? 1440), height: Number(process.env.HEIGHT ?? 1000), deviceScaleFactor: 1, mobile: Number(process.env.WIDTH ?? 1440) < 600 })
await send('Page.navigate', { url: `${BASE}/` }); await wait(1500)
await send('Runtime.evaluate', { expression: `localStorage.setItem('farmalidacion.theme', '${theme}'); localStorage.setItem('farmalidacion.reviewer', '${process.env.REVIEWER ?? ''}')` })
for (const route of routes) {
  if (process.env.SLOW) { await send('Network.enable'); await send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 }); await send('Network.setBlockedURLs', { urls: ['*:8000/*'] }) }
  await send('Page.navigate', { url: `${BASE}/?r=${Math.random()}#/${route}` }); await wait(Number(process.env.WAIT ?? 6000))
  if (process.env.CLICK) { await send('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(process.env.CLICK)})?.click()` }); await wait(3000) }
  const { data } = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(`${out}/${theme}-${route.replaceAll('/', '-')}.png`, Buffer.from(data, 'base64'))
}
ws.close(); chrome.kill(); process.exit(0)
