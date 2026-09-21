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
                request.branches.some(branch => !/^\/org\/gnome\/shell\/extensions\/[a-zA-Z0-9_-]+\/$/.test(branch)) ||
                [...request.enabled, ...request.disabled].some(uuid => typeof uuid !== 'string' || !uuid))
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
                await host.run(['dconf', 'reset', '-f', branch]);
                this.check(operation);
            }
            for (const key of target.keys())
                operation.touched.add(key);
            await host.run(['dconf', 'load', '/'], request.settings);
            this.check(operation);
            const completion = await host.complete(request);
            this.check(operation);
            if (!completion.ok)
                throw new Error(completion.error || 'layout activation failed');
            for (const [key, value] of [[DISABLED, request.disabled], [ENABLED, request.enabled]]) {
                await host.run(['dconf', 'write', key, `@as ${JSON.stringify(value)}`]);
                this.check(operation);
            }
            await this._verify(new Map([
                [ENABLED, `@as ${JSON.stringify(request.enabled)}`],
                [DISABLED, `@as ${JSON.stringify(request.disabled)}`],
            ]));
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

    async _restore(operation, membership) {
        const saved = new Map();
        const errors = [];
        for (const key of operation.touched) {
            if (SWITCH_KEYS.has(key) !== membership)
                continue;
            this.check(operation);
            if (operation.previous.has(key))
                saved.set(key, operation.previous.get(key));
            else {
                try { await this.host.run(['dconf', 'reset', key]); }
                catch (error) { errors.push(String(error)); }
            }
        }
        if (saved.size) {
            this.check(operation);
            try { await this.host.run(['dconf', 'load', '/'], serialize(saved)); }
            catch (error) { errors.push(String(error)); }
        }
        if (errors.length)
            throw new Error(errors.join('; '));
    }

    async _verify(expected) {
        const current = dumpValues(await this.host.run(['dconf', 'dump', '/']));
        const mismatches = [...expected].filter(([key, value]) =>
            !this.host.equal(current.get(key), value)).map(([key]) => key);
        if (mismatches.length)
            throw new Error(`settings verification failed: ${mismatches.join(', ')}`);
    }
}
