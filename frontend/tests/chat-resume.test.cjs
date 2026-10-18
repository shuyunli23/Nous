const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

// Exercise the page's effects with controlled API promises, without a browser
// or backend. JSX stays inspectable so loading/empty-state flashes are tested.
const compiled = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, '../src/pages/ChatPage.tsx'), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } },
).outputText;

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function mount({ routeId, state, list, detail, send } = {}) {
  const slots = [], effects = [], navigations = [], requests = [];
  let cursor = 0, tree, dirty = false;
  const t = (key) => key;
  const modes = [{ id: 'mode', key: 'workbench' }];
  const hooks = {
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial;
      return [slots[index], (value) => {
        const next = typeof value === 'function' ? value(slots[index]) : value;
        if (!Object.is(next, slots[index])) { slots[index] = next; dirty = true; }
      }];
    },
    useRef(value) { const index = cursor++; return slots[index] ??= { current: value }; },
    useCallback(fn) { cursor++; return fn; },
    useEffect(fn, deps) {
      const index = cursor++;
      if (!slots[index] || deps.some((value, i) => !Object.is(value, slots[index].deps[i]))) {
        slots[index]?.cleanup?.();
        slots[index] = { deps };
        effects.push(() => { slots[index].cleanup = fn(); });
      }
    },
  };
  const dependencies = {
    react: hooks,
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
    'react-router-dom': { useParams: () => ({ id: routeId }), useLocation: () => ({ state }), useNavigate: () => (...args) => navigations.push(args) },
    '../i18n': { useI18n: () => ({ t, messages: { chat: { suggestions: [] } } }) },
    '../api/client': { ApiError: class ApiError extends Error {} },
    '../api/types': { isChatProviderKind: () => true },
    '../api/llmConfig': { getLLMConfig: async () => ({ providers: [] }) },
    '../api/chatModes': { listChatModes: async () => modes },
    '../api/chat': { sendMessageStream: send ?? (async () => ({ conversation_id: 'recent', used_skills: [] })) },
    '../api/conversations': {
      listConversations: async (params) => { requests.push(['list', params]); return list ? list() : { items: [{ id: 'recent' }] }; },
      getConversation: async (id) => { requests.push(['detail', id]); return detail ? detail(id) : { id, title: 'Recent conversation', status: 'active', messages: [{ id: 'm1', content: 'Existing message', role: 'user' }] }; },
    },
  };
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    require: (name) => dependencies[name] ?? { default: name.split('/').pop() },
  });
  function render() {
    cursor = 0; dirty = false; tree = exports.default();
    while (effects.length) effects.shift()();
  }
  render();
  return {
    requests, navigations,
    async flush() {
      for (let i = 0; i < 12; i++) {
        await new Promise(setImmediate);
        if (dirty) render();
      }
    },
    nodes(type) {
      const found = [];
      function visit(node) {
        if (!node || typeof node !== 'object') return;
        if (Array.isArray(node)) return node.forEach(visit);
        if (node.type === type) found.push(node.props);
        visit(node.props?.children);
      }
      visit(tree); return found;
    },
    unmount() { slots.forEach((slot) => slot?.cleanup?.()); },
  };
}

test('workbench keeps one loading state until the latest conversation is ready, without redirecting', async () => {
  const pending = deferred();
  const page = mount({ detail: () => pending.promise });
  await page.flush();
  assert.equal(page.nodes('MessageList').length, 0);
  assert.equal(page.nodes('OverflowTitle')[0].text, 'common.loading');
  assert.equal(page.nodes('NewChatDialog').length, 0);
  pending.resolve({ id: 'recent', title: 'Recent', status: 'active', messages: [{ id: 'm1', content: 'Existing message' }] });
  await page.flush();
  assert.equal(page.nodes('MessageList')[0].messages[0].content, 'Existing message');
  assert.equal(page.nodes('OverflowTitle')[0].text, 'Recent');
  assert.deepEqual(page.navigations, []);
  assert.equal(page.requests.filter(([kind]) => kind === 'detail').length, 1);
});

test('direct conversation links load that conversation without showing the new-chat screen', async () => {
  const page = mount({ routeId: 'chosen' });
  assert.equal(page.nodes('MessageList').length, 0);
  await page.flush();
  assert.deepEqual(page.requests, [['detail', 'chosen']]);
  assert.equal(page.nodes('MessageList')[0].messages.length, 1);
});

test('an empty history opens the new-chat picker, but a loading failure does not', async () => {
  const empty = mount({ list: async () => ({ items: [] }) });
  await empty.flush();
  assert.equal(empty.nodes('NewChatDialog').length, 1);
  const failed = mount({ list: async () => { throw new Error('offline'); } });
  await failed.flush();
  assert.equal(failed.nodes('NewChatDialog').length, 0);
});

test('explicit new-chat navigation does not resume an existing conversation', async () => {
  const page = mount({ state: { confirmedNew: true, modeId: 'mode' } });
  await page.flush();
  assert.deepEqual(page.requests, []);
  assert.equal(page.nodes('MessageInput')[0].disabled, false);
});

test('leaving while the recent-chat lookup is pending does not fetch its detail', async () => {
  const pending = deferred();
  const page = mount({ list: () => pending.promise });
  page.unmount();
  pending.resolve({ items: [{ id: 'recent' }] });
  await page.flush();
  assert.equal(page.requests.filter(([kind]) => kind === 'detail').length, 0);
});

test('continuing a resumed chat does not introduce a delayed redirect after sending', async () => {
  for (const send of [undefined, async () => { throw new Error('offline'); }]) {
    const page = mount({ send });
    await page.flush();
    await page.nodes('MessageInput')[0].onSend('Continue');
    await page.flush();
    assert.deepEqual(page.navigations, []);
  }
});
