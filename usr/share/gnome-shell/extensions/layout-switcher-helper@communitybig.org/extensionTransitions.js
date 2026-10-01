// SPDX-License-Identifier: MIT

// Shared by current and legacy helpers; callers retain their layout ordering.
export class ExtensionTransitions {
    constructor(helper, manager, steps, delay) {
        this.helper = helper;
        this.manager = manager;
        this.steps = steps;
        this.delay = delay;
    }

    async detachReloads(order, reload, live, target) {
        for (const uuid of order) {
            if (!reload.has(uuid) || !live.has(uuid) || !target.has(uuid))
                continue;
            try {
                this.manager.disableExtension(uuid);
                await this.helper._waitState(this.manager, uuid, state => this.helper._isDown(state)); // NOSONAR: S9382 - Shell transitions must settle in order.
                this.steps.push(`reload-off ${uuid}`);
            } catch (error) {
                this.steps.push(`reload-off ${uuid} ERR ${error}`);
            }
            await this.helper._sleep(this.delay); // NOSONAR: S9382 - yield before the next Shell transition.
        }
    }

    async disableLeaving(live, target, teardown) {
        // Reverse load order minimizes Shell rebase cycles.
        const leaving = [...live].filter(uuid => !target.has(uuid)).reverse();
        for (const uuid of leaving) {
            try {
                if (teardown.has(uuid)) {
                    await this.helper._reloadOne(this.manager, uuid); // NOSONAR: S9382 - recreate actors before disabling them.
                    this.steps.push(`teardown-reload ${uuid}`);
                    await this.helper._sleep(this.delay); // NOSONAR: S9382 - wait for recreated actors before disabling.
                }
                const accepted = this.manager.disableExtension(uuid);
                await this.helper._waitState(this.manager, uuid, state => this.helper._isDown(state)); // NOSONAR: S9382 - Shell transitions must settle in order.
                this.steps.push(accepted === false ? `disable ${uuid} REJECTED` : `disable ${uuid}`);
            } catch (error) {
                this.steps.push(`disable ${uuid} ERR ${error}`);
            }
            await this.helper._sleep(this.delay); // NOSONAR: S9382 - yield before the next Shell transition.
        }
    }

    async enableMissing(order) {
        const live = this.helper._liveUuids(this.manager);
        for (const uuid of order) {
            if (live.has(uuid))
                continue;
            try {
                const accepted = this.manager.enableExtension(uuid);
                await this.helper._waitState(this.manager, uuid, state => this.helper._isSettledUp(state)); // NOSONAR: S9382 - Shell transitions must settle in order.
                this.steps.push(accepted === false ? `enable ${uuid} REJECTED` : `enable ${uuid}`);
            } catch (error) {
                this.steps.push(`enable ${uuid} ERR ${error}`);
            }
            await this.helper._sleep(this.delay); // NOSONAR: S9382 - yield before the next Shell transition.
        }
    }
}
