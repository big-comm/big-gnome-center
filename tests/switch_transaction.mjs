// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_HELPER_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_HELPER_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/', import.meta.url);
const {SwitchTransaction, dumpValues} = await import(new URL('switchTransaction.js', root));
const enabled = '/org/gnome/shell/enabled-extensions';
const disabled = '/org/gnome/shell/disabled-extensions';
const branch = '/org/gnome/shell/extensions/owned/';
const original = new Map([[`${branch}old`, "'before'"], ['/other/keep', '42'],
    [enabled, "['helper', 'previous']"], [disabled, '@as []']]);
const serialize = values => [...values].map(([key, value]) => {
    const index = key.lastIndexOf('/');
    return `[${key.slice(1, index)}]\n${key.slice(index + 1)}=${value}\n`;
}).join('\n');
const request = () => ({branches: [branch], enabled: ['helper', 'target'], disabled: [],
    settings: '[org/gnome/shell/extensions/owned]\nnew=true\n', label: 'Target'});
const canonical = value => value?.replace(/^@as\s+/, '').replaceAll('"', "'");
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; };
function harness(failure = '') {
    const values = new Map(original), timers = new Map(), watches = new Map(), events = [];
    let live = ['helper', 'previous'], label = 'Previous', failOnce = true, nextId = 0;
    const hooks = new Map();
    const point = async name => {
        events.push(name); await hooks.get(name)?.();
        if (name === failure && failOnce) { failOnce = false; throw new Error(`injected ${name}`); }
    };
    const host = {
        async run(argv, input) {
            if (argv[1] === 'dump') { await point('dump'); return serialize(values); }
            if (argv[1] === 'reset') {
                const path = argv.at(-1);
                for (const key of [...values.keys()])
                    if (key === path || (argv.includes('-f') && key.startsWith(path))) values.delete(key);
            } else if (argv[1] === 'load') {
                for (const [key, value] of dumpValues(input)) values.set(key, value);
            } else if (argv[1] === 'write') values.set(argv[2], argv[3]);
            await point(argv[1] === 'write' ? `write:${argv[2]}` : argv[1]);
            return '';
        },
        live: () => [...live], label: () => label,
        async begin() { live = ['helper']; await point('begin'); },
        async complete(req) { live = [...req.enabled]; label = req.label; await point('complete'); return {ok: true, steps: ['done']}; },
        async stop() { live = ['helper']; await point('stop'); },
        async restore(previous, oldLabel) { live = [...previous]; label = oldLabel; await point('restore'); },
        async finish() { await point('finish'); },
        release() { events.push('release'); },
        arm(ms, callback) { const id = ++nextId; timers.set(id, callback); return id; },
        disarm(id) { timers.delete(id); },
        watch(callback) { const id = ++nextId; watches.set(id, callback); return id; },
        unwatch(id) { watches.delete(id); },
        equal: (a, b) => canonical(a) === canonical(b), warn() {},
    };
    const transaction = new SwitchTransaction(host);
    const recovered = () => {
        assert.deepEqual(values, original); assert.deepEqual(live, ['helper', 'previous']);
        assert.equal(label, 'Previous');
    };
    const clean = () => {
        assert.equal(transaction.current, null); assert.equal(timers.size, 0); assert.equal(watches.size, 0);
    };
    return {host, transaction, hooks, events, values, timers, watches, recovered, clean,
        live: () => live};
}
let count = 0;
async function test(name, callback) {
    try { await callback(); count++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
}
await test('success commits settings and membership', async () => {
    const h = harness(), result = await h.transaction.apply(request(), ':1.1');
    assert.equal(result.ok, true); assert.equal(h.values.get(branch + 'new'), 'true');
    assert.ok(!h.values.has(branch + 'old')); assert.equal(h.values.get('/other/keep'), '42');
    assert.deepEqual(h.live(), ['helper', 'target']); h.clean();
});
for (const point of ['begin', 'reset', 'load', 'complete', `write:${disabled}`, `write:${enabled}`, 'finish']) {
    await test(`recover failure after ${point}`, async () => {
        const h = harness(point), result = await h.transaction.apply(request(), ':1.1');
        assert.equal(result.ok, false); assert.equal(result.recovered, true);
        assert.match(result.error, /injected/); h.recovered(); h.clean();
    });
}
await test('snapshot failure never tears down', async () => {
    const h = harness('dump'), result = await h.transaction.apply(request(), ':1.1');
    assert.equal(result.ok, false); assert.ok(!h.events.includes('begin')); h.recovered(); h.clean();
});
for (const phase of ['begin', 'load', 'complete', 'finish']) {
    for (const mode of ['abort', 'deadline', 'caller-loss']) {
        await test(`${mode} waits for owned work at ${phase}`, async () => {
            const h = harness(), started = deferred(), gate = deferred();
            h.hooks.set(phase, async () => { started.resolve(); await gate.promise; });
            const work = h.transaction.apply(request(), ':1.1'); await started.promise;
            const oldTimer = [...h.timers.values()][0], oldWatch = [...h.watches.values()][0];
            if (mode === 'abort') assert.equal(h.transaction.cancel(), work);
            if (mode === 'deadline') oldTimer();
            if (mode === 'caller-loss') oldWatch(':1.1');
            const rejected = await h.transaction.apply(request(), ':1.2');
            assert.equal(rejected.ok, false); assert.equal(h.events.includes('stop'), false);
            gate.resolve(); const result = await work;
            assert.equal(result.ok, false); assert.equal(result.recovered, true); h.recovered(); h.clean();
            h.hooks.clear();
            h.hooks.set('begin', () => { oldTimer(); oldWatch(':1.1'); });
            assert.equal((await h.transaction.apply(request(), ':1.1')).ok, true); h.clean();
        });
    }
}
await test('another caller disappearing does not cancel owner', async () => {
    const h = harness(); h.hooks.set('begin', () => [...h.watches.values()][0](':1.2'));
    assert.equal((await h.transaction.apply(request(), ':1.1')).ok, true); h.clean();
});
for (const point of ['stop', 'restore', 'load']) {
    await test(`recovery error remains visible: ${point}`, async () => {
        const h = harness('complete');
        const originalMethod = h.host[point === 'load' ? 'run' : point];
        if (point === 'load') h.host.run = async (argv, input) => {
            if (h.transaction.current.recovering && argv[1] === 'load') throw new Error('cannot restore settings');
            return originalMethod(argv, input);
        };
        else h.host[point] = async () => { throw new Error('cannot recover extensions'); };
        const result = await h.transaction.apply(request(), ':1.1');
        assert.equal(result.ok, false); assert.equal(result.recovered, false);
        assert.match(result.error, /recovery incomplete/); h.clean();
    });
}
await test('silent final write failure is detected', async () => {
    const h = harness(); h.hooks.set(`write:${enabled}`, () => h.values.set(enabled, "['wrong']"));
    const result = await h.transaction.apply(request(), ':1.1');
    assert.equal(result.ok, false); assert.match(result.error, /verification failed/); h.recovered(); h.clean();
});
await test('unattempted settings retain concurrent changes', async () => {
    const h = harness('reset'); h.values.set('/other/untouched', '0');
    h.hooks.set('reset', () => h.values.set('/other/untouched', '1'));
    const result = await h.transaction.apply(request(), ':1.1');
    assert.equal(result.recovered, true); assert.equal(h.values.get('/other/untouched'), '1'); h.clean();
});
for (const invalid of [null, {}, {branches: ['/'], enabled: [], disabled: [], settings: ''},
    {...request(), settings: '[org/gnome/shell]\nenabled-extensions=[]\n'}]) {
    await test('invalid request cannot mutate desktop', async () => {
        const h = harness(); assert.equal((await h.transaction.apply(invalid, ':1.1')).ok, false);
        assert.ok(!h.events.includes('begin')); h.recovered(); h.clean();
    });
}
await test('structured variants survive scoped recovery', async () => {
    const h = harness('complete');
    h.values.set(branch + 'value', "{'key': <[1, 2]>}");
    const result = await h.transaction.apply(request(), ':1.1');
    assert.equal(result.recovered, true); assert.equal(h.values.get(branch + 'value'), "{'key': <[1, 2]>}"); h.clean();
});
console.log(`${count} switch transaction scenarios passed`);
