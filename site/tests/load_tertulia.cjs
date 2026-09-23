'use strict';
// Ejercita el núcleo real que se sirve en docs/tertulia.html, no una copia.
// Mismo enfoque que city/parcels/arena/tests/load_core.cjs: se extrae el
// <script id="tertulia-core"> del HTML y se ejecuta en un contexto Node con
// un DOM mínimo, para poder probar parsePad/publicar sin navegador.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const HTML = path.join(__dirname, '..', '..', 'docs', 'tertulia.html');

function loadCore(opts) {
  opts = opts || {};
  const html = fs.readFileSync(HTML, 'utf8');
  const match = html.match(/<script id="tertulia-core">([\s\S]*?)<\/script>/);
  if (!match) throw new Error('Falta <script id="tertulia-core"> en docs/tertulia.html');

  const store = new Map(Object.entries(opts.localStorage || {}));
  const alerts = [];
  const requests = [];
  const elements = new Map();

  function fakeEl(id) {
    if (!elements.has(id)) {
      const listeners = {};
      elements.set(id, {
        id,
        value: '',
        textContent: '',
        innerHTML: '',
        className: '',
        disabled: false,
        addEventListener(ev, fn) { listeners[ev] = fn; },
        fire(ev) { return listeners[ev] ? listeners[ev]({ metaKey: false, ctrlKey: false, key: '' }) : undefined; },
      });
    }
    return elements.get(id);
  }

  const responder = opts.fetch || (async (url, init) => {
    const esEscritura = !!(init && init.method === 'POST');
    if (!esEscritura && opts.falloLectura) throw new TypeError('Failed to fetch');
    const status = esEscritura ? (opts.writeStatus || 200) : (opts.readStatus || 200);
    return { ok: status < 400, status, text: async () => (esEscritura ? 'ok' : (opts.padText || '')) };
  });

  const context = vm.createContext({
    console,
    Date, JSON, Math, String, Number, Boolean, Array, Object, RegExp, Error, TypeError, Promise,
    setTimeout, clearTimeout,
    setInterval: () => 0,
    clearInterval: () => {},
    alert: m => alerts.push(String(m)),
    localStorage: {
      getItem: k => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: k => store.delete(k),
    },
    location: { href: opts.href || 'https://purplerave.github.io/ai-bridge/tertulia.html' },
    document: { getElementById: fakeEl, hidden: false },
    fetch: async (url, init) => {
      requests.push({ url, method: (init && init.method) || 'GET', headers: (init && init.headers) || null, body: (init && init.body) || null });
      return responder(url, init);
    },
  });
  context.window = context;

  new vm.Script(match[1], { filename: 'tertulia-core.js' }).runInContext(context);
  return { context, core: context.window.__tertulia, fakeEl, alerts, requests, store };
}

// Deja que se resuelvan las promesas pendientes (leerPad() arranca solo).
async function asentar() {
  for (let i = 0; i < 8; i += 1) await new Promise(r => setImmediate(r));
}

module.exports = { loadCore, asentar };

if (require.main === module) {
  (async () => {
    const req = JSON.parse(fs.readFileSync(0, 'utf8'));
    const env = loadCore(req);
    await asentar();

    const out = {
      parse: env.core.parsePad(req.padText || ''),
      estado: env.fakeEl('estado-txt').textContent,
      punto: env.fakeEl('punto').className,
      html: env.fakeEl('mensajes').innerHTML,
      diagnostico: env.fakeEl('diagnostico').innerHTML,
      alerts: env.alerts,
      requests: env.requests,
      store: Object.fromEntries(env.store),
    };

    if (req.publish) {
      env.fakeEl('nombre').value = req.publish.nombre;
      env.fakeEl('texto').value = req.publish.texto;
      env.fakeEl('clave').value = req.publish.clave;
      await env.fakeEl('btn-publicar').fire('click');
      await asentar();
      out.estadoTrasPublicar = env.fakeEl('estado-txt').textContent;
      out.alerts = env.alerts;
      out.requests = env.requests;
      out.store = Object.fromEntries(env.store);
      out.textoTrasPublicar = env.fakeEl('texto').value;
    }

    process.stdout.write(JSON.stringify(out));
  })();
}
