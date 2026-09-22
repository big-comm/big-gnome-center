// SPDX-License-Identifier: MIT

const ENABLED = '/org/gnome/shell/enabled-extensions';
const DISABLED = '/org/gnome/shell/disabled-extensions';
const SWITCH_KEYS = new Set([ENABLED, DISABLED]);

export function dumpValues(text) {
    const values = new Map();
    let section = null;
    for (const raw of text.split('\n')) {
        const line = raw.trim();
        if (!line || line.startsWith('#') || line.startsWith(';'))
            continue;
        if (line.startsWith('[') && line.endsWith(']')) {
            section = line.slice(1, -1).replace(/^\/+|\/+$/g, '');
            continue;
        }
        const separator = line.indexOf('=');
        if (section !== null && separator > 0)
            values.set(`/${[section, line.slice(0, separator).trim()].filter(Boolean).join('/')}`,
                line.slice(separator + 1));
    }
    return values;
}

function serialize(values) {
    return [...values].map(([path, value]) => {
        const index = path.lastIndexOf('/');
        return `[${path.slice(1, index) || '/'}]\n${path.slice(index + 1)}=${value}\n`;
    }).join('\n');
}

export class SwitchTransaction {
    constructor(host) {
        this.host = host;
        this.current = null;
    }

    check(operation = this.current) {
        if (!operation || this.current !== operation || operation.reason)
            throw new Error(operation?.reason || 'retired layout switch');
    }

    cancel(reason = 'layout switch cancelled') {
        const operation = this.current;
        if (operation && !operation.recovering)
            operation.reason ||= reason;
        return operation?.promise;
    }

    apply(request, sender) {
        if (this.current)
            return Promise.resolve({ok: false, error: 'layout switch already in progress'});
        const operation = {request, sender, reason: '', recovering: false, mutated: false};
        this.current = operation;
        operation.promise = this._apply(operation);
        return operation.promise;
    }

    async _apply(operation) {
        const host = this.host;
        let timer, watch;
        let result;
        try {
            const request = operation.request;
            if (!Array.isArray(request.branches) || !Array.isArray(request.enabled) ||
                !Array.isArray(request.disabled) || typeof request.settings !== 'string' ||
                (request.persist !== undefined && !Array.isArray(request.persist)) ||
                request.branches.some(branch => !/^\/org\/gnome\/shell\/extensions\/[a-zA-Z0-9_-]+\/$/.test(branch)) ||
                [...request.enabled, ...request.disabled, ...(request.persist ?? [])]
                    .some(uuid => typeof uuid !== 'string' || !uuid))
                throw new Error('invalid layout switch request');
            const target = dumpValues(request.settings);
            if ([...target.keys()].some(key => SWITCH_KEYS.has(key)))
                throw new Error('extension membership must be applied separately');

            timer = host.arm(120000, () => {
                if (this.current === operation)
                    this.cancel('layout switch deadline exceeded');
            });
            watch = host.watch(sender => {
                if (this.current === operation && sender === operation.sender)
                    this.cancel('layout switch caller disappeared');
            });
            operation.previous = dumpValues(await host.run(['dconf', 'dump', '/']));
            this.check(operation);
            operation.live = host.live();
            operation.label = host.label();
            operation.touched = new Set(SWITCH_KEYS);
            operation.mutated = true;
            await host.begin(request);
            this.check(operation);
            for (const branch of request.branches) {
                for (const path of operation.previous.keys()) {
                    if (path.startsWith(branch))
                        operation.touched.add(path);
                }
            }
            for (const key of target.keys())
                operation.touched.add(key);
            await host.mutate(request.branches, request.settings);
            this.check(operation);
            const completion = await host.complete(request);
            this.check(operation);
            if (!completion.ok)
                throw new Error(completion.error || 'layout activation failed');
            this._verifyLive(request.enabled, completion.optionalFailures ?? []);
            this.check(operation);
            await host.finish();
            this.check(operation);
            result = {
                ok: true,
                steps: completion.steps,
                optionalFailures: completion.optionalFailures ?? [],
                recovered: false,
                error: '',
            };
        } catch (error) {
            operation.recovering = true;
            operation.reason = '';
            if (timer !== undefined)
                host.disarm(timer);
            timer = host.arm(120000, () => { operation.reason = 'layout recovery deadline exceeded'; });
            const errors = [];
            if (operation.mutated) {
                const attempt = async callback => {
                    try { await callback(); } catch (failure) { errors.push(String(failure)); }
                };
                await attempt(() => host.stop());
                await attempt(() => this._restore(operation, false));
                await attempt(() => host.restore(operation.live, operation.label));
                await attempt(() => this._restore(operation, true));
                await attempt(() => this._verify(new Map([...operation.touched]
                    .map(key => [key, operation.previous.get(key)]))));
            }
            result = {ok: false, recovered: operation.mutated && errors.length === 0,
                error: `${error}${errors.length ? `; recovery incomplete: ${errors.join('; ')}` : ''}`};
        } finally {
            try { if (timer !== undefined) host.disarm(timer); } catch (error) { host.warn(error); }
            try { if (watch !== undefined) host.unwatch(watch); } catch (error) { host.warn(error); }
            try { host.release(); } catch (error) {
                result = {ok: false, recovered: false, error: `${result?.error || ''}; cleanup: ${error}`};
            }
            if (this.current === operation)
                this.current = null;
        }
        return result;
    }

    _verifyLive(expected, optionalFailures = []) {
        const optional = new Set(optionalFailures);
        const wanted = new Set(expected.filter(uuid => !optional.has(uuid)));
        const actual = new Set(this.host.live());
        const missing = [...wanted].filter(uuid => !actual.has(uuid));
        const extra = [...actual].filter(uuid => !wanted.has(uuid));
        if (missing.length || extra.length) {
            throw new Error(`extension verification failed: missing ${missing.join(', ') || '-'}; ` +
                `extra ${extra.join(', ') || '-'}`);
        }
    }

    async _restore(operation, membership) {
        const saved = new Map();
        const reset = [];
        for (const key of operation.touched) {
            if (SWITCH_KEYS.has(key) !== membership)
                continue;
            this.check(operation);
            if (operation.previous.has(key))
                saved.set(key, operation.previous.get(key));
            else
                reset.push(key);
        }
        this.check(operation);
        await this.host.restoreValues(reset, serialize(saved));
        this.check(operation);
    }

    async _verify(expected) {
        let mismatches = [];
        for (let attempt = 0; attempt < 10; attempt++) {
            const current = dumpValues(await this.host.run(['dconf', 'dump', '/']));
            mismatches = [...expected].filter(([key, value]) => {
                if (key === DISABLED && this.host.disabledMatches)
                    return !this.host.disabledMatches(
                        current.get(key), value, expected.get(ENABLED));
                return !this.host.equal(current.get(key), value);
            }).map(([key]) => key);
            if (!mismatches.length)
                return;
            if (attempt < 9)
                await this.host.settle(50);
        }
        throw new Error(`settings verification failed: ${mismatches.join(', ')}`);
    }
}
