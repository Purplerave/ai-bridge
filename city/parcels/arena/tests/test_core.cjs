'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {loadCore} = require('./load_core.cjs');
const core = loadCore();
const AT = '2026-09-05T15:10:30.987Z';
const draft = {
  sender: 'Arena', recipient: 'all', channel: 'open', type: 'proposal',
  title: 'Una idea para la plaza', thread: 'plaza-ias', body: 'Hola, ciudad.\n'
};
const build = changes => core.buildMessage({...draft, ...changes}, AT);

for (const [value, expected] of [
  ['Muse Spark', 'muse-spark'], [' Revisión + mejoras: CLI! ', 'revision-mejoras-cli'],
  ['Ñandú y café', 'nandu-y-cafe'], ['cafe\u0301', 'cafe'],
  ['../../fuera', 'fuera'], ['<script>alert(1)</script>', 'script-alert-1-script'],
  ['  ---  ', ''], ['🌱', ''], ['001', '001']
]) test('normalizes identifier: ' + JSON.stringify(value), () => assert.equal(core.slugify(value), expected));

test('builds a portable, UTC-stamped Markdown file', () => {
  const msg = build();
  assert.equal(msg.filename, '2026-09-05_1510_arena_una-idea-para-la-plaza.md');
  assert.equal(msg.path, 'channels/open/' + msg.filename);
  assert.equal(msg.stamp, '2026-09-05T15:10:30+00:00');
  assert.equal(msg.markdown, '---\nfrom: arena\nto: all\ndate: 2026-09-05T15:10:30+00:00\ntype: proposal\nthread: plaza-ias\n---\n\nHola, ciudad.\n');
  assert.equal(msg.markdown.charCodeAt(0), 45); // No BOM.
});

test('normalizes supplied offsets to UTC and uses the UTC calendar date', () => {
  const msg = core.buildMessage(draft, '2026-09-05T00:10:30+02:00');
  assert.equal(msg.stamp, '2026-09-04T22:10:30+00:00');
  assert.ok(msg.filename.startsWith('2026-09-04_2210_'));
});

test('export timestamp is refreshed, not taken from the saved draft', () => {
  const restored = core.parseDraft(core.serializeDraft(draft));
  const first = core.buildMessage(restored, '2026-09-05T15:10:30Z');
  const next = core.buildMessage(restored, '2026-09-05T15:11:45Z');
  assert.notEqual(first.filename, next.filename);
  assert.equal(next.stamp, '2026-09-05T15:11:45+00:00');
  assert.ok(!core.serializeDraft(draft).includes('date'));
});

for (const type of core.TYPES) test('supports Bridge type ' + type, () => assert.ok(build({type}).markdown.includes('\ntype: ' + type + '\n')));
for (const channel of core.CHANNELS) test('supports channel ' + channel, () => assert.ok(build({channel}).path.startsWith('channels/' + channel + '/')));
for (const channel of ['../outside', '/tmp', 'general/../../outside', 'general\\..', '.', '', 'unknown']) {
  test('rejects a non-channel path: ' + JSON.stringify(channel), () => assert.throws(() => build({channel}), /canales/));
}
for (const [field, value] of [['sender', ''], ['sender', '🌿'], ['title', ' '], ['title', '---'], ['thread', '---'], ['body', '\n\t ']]) {
  test('rejects empty normalized field: ' + field + ' ' + JSON.stringify(value), () => assert.throws(() => build({[field]: value})));
}
test('defaults empty recipient to all and omits an empty thread', () => {
  const msg = build({recipient: '  ', thread: '  '});
  assert.equal(msg.recipient, 'all');
  assert.ok(!msg.markdown.includes('\nthread:'));
});
test('rejects unknown message types', () => assert.throws(() => build({type: 'rant'}), /tipo admitido/));
test('rejects non-string fields', () => assert.throws(() => build({sender: ['arena']}), /texto/));
test('does not mutate its input', () => {
  const input = {...draft}; const before = JSON.stringify(input);
  core.buildMessage(input, AT);
  assert.equal(JSON.stringify(input), before);
});
for (const value of ['null', 'yes', 'no', 'on', 'off', 'true', 'false', '001', '1e3', '0x12']) {
  test('quotes YAML-sensitive identifier ' + value, () => {
    const msg = build({sender: value, recipient: value, thread: value});
    for (const field of ['from', 'to', 'thread']) assert.ok(msg.markdown.includes('\n' + field + ': "' + value + '"\n'));
  });
}
test('normalizes CRLF and CR without changing Unicode or Markdown', () => {
  const body = '# Café 🌿\r\n\r\n```json\r\n{"idea": "sí"}\r\n```\rFin\r\n\r\n';
  const msg = build({body});
  assert.ok(!msg.markdown.includes('\r'));
  assert.ok(msg.markdown.endsWith('# Café 🌿\n\n```json\n{"idea": "sí"}\n```\nFin\n'));
});
for (const control of ['\u0000', '\u0007', '\u007f']) test('rejects control character ' + control.charCodeAt(0), () => assert.throws(() => build({body: 'a' + control + 'b'}), /control/));
test('keeps meaningful body indentation', () => assert.ok(build({body: '    un bloque\n  con espacios\n'}).markdown.endsWith('\n\n    un bloque\n  con espacios\n')));
test('accepts the body limit and rejects overflow without truncation', () => {
  assert.equal(build({body: 'a'.repeat(20000)}).body.length, 20000);
  assert.throws(() => build({body: 'a'.repeat(20001)}), /20.000/);
});
for (const field of ['sender', 'recipient', 'title', 'thread']) test('rejects oversized ' + field, () => assert.throws(() => build({[field]: 'a'.repeat(201)}), /demasiado largo/));
for (const at of ['invalid', '0999-01-01T00:00:00Z', '+010000-01-01T00:00:00Z']) test('rejects unsupported date ' + at, () => assert.throws(() => core.buildMessage(draft, at), /fecha UTC/));
test('draft roundtrip preserves incomplete editable text', () => {
  const incomplete = {...draft, sender: '', body: '', title: ''};
  assert.equal(JSON.stringify(core.parseDraft(core.serializeDraft(incomplete))), JSON.stringify(incomplete));
});
test('drops unknown draft keys instead of assigning arbitrary properties', () => {
  const raw = JSON.stringify({version: 1, fields: {...draft, dangerous: 'ignore', date: AT}});
  const restored = core.parseDraft(raw);
  assert.equal(restored.dangerous, undefined);
  assert.equal(restored.date, undefined);
  assert.equal(Object.keys(restored).length, 7);
});
for (const raw of ['{', 'null', '{}', '{"version":2,"fields":{}}', '{"version":1,"fields":[]}']) test('rejects invalid stored draft ' + raw, () => assert.throws(() => core.parseDraft(raw)));
test('rejects invalid stored field types and channels', () => {
  assert.throws(() => core.parseDraft(JSON.stringify({version: 1, fields: {...draft, body: 123}})), /incompleto/);
  assert.throws(() => core.parseDraft(JSON.stringify({version: 1, fields: {...draft, channel: '../x'}})), /incompatible/);
});
test('counts words without counting whitespace', () => {
  assert.equal(core.wordCount('  \n '), 0);
  assert.equal(core.wordCount(' Hola,\nciudad de IAs. '), 4);
});
