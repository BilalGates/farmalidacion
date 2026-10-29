// Agrupa los estilos calculados de botones, campos y recuadros de varias rutas
// para detectar variantes que deberían ser la misma pieza.
//   node scripts/ui/auditar-controles.mjs <ruta>...
import { spawn } from 'node:child_process'
const CHROME = process.env.CHROME ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = process.env.BASE_URL ?? 'http://localhost:5173'
const routes = process.argv.slice(2)
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--remote-debugging-port=9336', `--user-data-dir=${process.env.TEMP}/audit-chrome`, '--window-size=1440,1000', 'about:blank'])
const wait = (ms) => new Promise(r => setTimeout(r, ms))
let target
for (let i = 0; i < 40 && !target; i++) { await wait(250); try { target = (await (await fetch('http://127.0.0.1:9336/json')).json()).find(t => t.type === 'page') } catch {} }
const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r)
let n = 0; const pending = new Map()
ws.onmessage = (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d.result); pending.delete(d.id) }
const send = (method, params = {}) => new Promise(r => { const id = ++n; pending.set(id, r); ws.send(JSON.stringify({ id, method, params })) })
await send('Page.enable')
await send('Page.navigate', { url: `${BASE}/` }); await wait(1500)
await send('Runtime.evaluate', { expression: `localStorage.setItem('farmalidacion.theme','light'); localStorage.setItem('farmalidacion.reviewer','jlopez')` })
const groups = { boton: new Map(), campo: new Map(), recuadro: new Map() }
const expr = `(() => {
  const out = []; const main = document.querySelector('main') || document.body
  const sig = (e, props) => { const s = getComputedStyle(e); return props.map(p => s[p]).join(' | ') }
  const label = e => (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).join('.') : e.tagName.toLowerCase()) + ' «' + (e.innerText || e.placeholder || e.value || '').trim().slice(0, 24) + '»'
  for (const e of main.querySelectorAll('button, a.button, [role=button]')) if (e.offsetParent) out.push(['boton', sig(e, ['height','paddingLeft','fontSize','fontWeight','borderTopWidth','borderTopColor','borderRadius','backgroundColor','color']), label(e)])
  for (const e of main.querySelectorAll('input:not([type=checkbox]):not([type=radio]), select, textarea')) if (e.offsetParent) out.push(['campo', sig(e, ['height','paddingLeft','fontSize','borderTopColor','borderRadius','backgroundColor']), label(e)])
  for (const e of main.querySelectorAll('section, article, aside, form, div')) { if (!e.offsetParent) continue; const s = getComputedStyle(e); if (s.borderTopWidth !== '0px' && s.borderTopStyle !== 'none' && s.borderLeftWidth !== '0px' && e.offsetWidth > 150 && e.offsetHeight > 40) out.push(['recuadro', sig(e, ['borderTopColor','borderRadius','backgroundColor','paddingTop','paddingLeft','boxShadow']), label(e)]) }
  return out })()`
for (const route of routes) {
  await send('Page.navigate', { url: `${BASE}/?a=${Math.random()}#/${route}` }); await wait(5000)
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true })
  for (const [kind, sig, label] of r.result.value ?? []) { const g = groups[kind]; if (!g.has(sig)) g.set(sig, { count: 0, where: new Set(), examples: new Set() }); const x = g.get(sig); x.count++; x.where.add(route); if (x.examples.size < 3) x.examples.add(label) }
}
for (const [kind, g] of Object.entries(groups)) {
  console.log(`\n=== ${kind}: ${g.size} variantes`)
  for (const [sig, x] of [...g.entries()].sort((a, b) => b[1].count - a[1].count)) console.log(`${String(x.count).padStart(3)}× ${sig}\n      en: ${[...x.where].slice(0, 4).join(', ')}  ej: ${[...x.examples].join(' ; ')}`)
}
ws.close(); chrome.kill(); process.exit(0)
