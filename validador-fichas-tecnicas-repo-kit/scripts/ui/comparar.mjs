// Compara píxel a píxel capturas homónimas de dos carpetas.
//   node scripts/ui/comparar.mjs <carpetaA> <carpetaB> <fichero.png>...
// Cuidado: dos capturas del mismo código pueden diferir en animaciones (p. ej. el
// panel de filtros); repite la captura antes de dar una diferencia por real.
import { spawn } from 'node:child_process'
import { readFileSync } from 'node:fs'
const CHROME = process.env.CHROME ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = process.env.BASE_URL ?? 'http://localhost:5173'
const [a, b, ...files] = process.argv.slice(2)
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--remote-debugging-port=9335', `--user-data-dir=${process.env.TEMP}/diff-chrome`, 'about:blank'])
const wait = (ms) => new Promise(r => setTimeout(r, ms))
let target
for (let i = 0; i < 160 && !target; i++) { await wait(250); try { target = (await (await fetch('http://127.0.0.1:9335/json')).json()).find(t => t.type === 'page') } catch {} }
const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r)
let n = 0; const pending = new Map()
ws.onmessage = (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d.result); pending.delete(d.id) }
const send = (method, params) => new Promise(r => { const id = ++n; pending.set(id, r); ws.send(JSON.stringify({ id, method, params })) })
for (const f of files) {
  const A = readFileSync(`${a}/${f}`).toString('base64'), B = readFileSync(`${b}/${f}`).toString('base64')
  const expr = `(async () => { const load = s => new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = 'data:image/png;base64,' + s })
    const [x, y] = await Promise.all([load('${A}'), load('${B}')]); const c = document.createElement('canvas'); c.width = x.width; c.height = x.height; const g = c.getContext('2d')
    g.drawImage(x, 0, 0); const p = g.getImageData(0, 0, c.width, c.height).data; g.drawImage(y, 0, 0); const q = g.getImageData(0, 0, c.width, c.height).data
    let d = 0, x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1; for (let i = 0; i < p.length; i += 4) if (p[i] !== q[i] || p[i+1] !== q[i+1] || p[i+2] !== q[i+2]) { d++; const k = i / 4, px = k % c.width, py = (k / c.width) | 0; x0 = Math.min(x0, px); y0 = Math.min(y0, py); x1 = Math.max(x1, px); y1 = Math.max(y1, py) }
    return d ? d + ' px en ' + [x0, y0, x1, y1] : 'idéntica' })()`
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })
  console.log(f, '→', r.result.value)
}
ws.close(); chrome.kill(); process.exit(0)
