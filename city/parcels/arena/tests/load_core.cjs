'use strict';
// Exercise the exact inline core shipped in the standalone HTML, not a copy.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function loadCore() {
  const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  const match = html.match(/<script id="mesa-core">([\s\S]*?)<\/script>/);
  if (!match) throw new Error('Missing inline mesa-core script');
  const context = vm.createContext({});
  new vm.Script(match[1], {filename: 'mesa-core.js'}).runInContext(context);
  return context.MesaBridge;
}

module.exports = {loadCore};

if (require.main === module) {
  const request = JSON.parse(fs.readFileSync(0, 'utf8'));
  const core = loadCore();
  const results = request.cases.map(fields => core.buildMessage(fields, request.at));
  process.stdout.write(JSON.stringify(results));
}
