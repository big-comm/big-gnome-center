// SPDX-License-Identifier: MIT
// A monitor-centered taskbar uses the free side instead of being clipped.
import assert from 'node:assert/strict';

import {
    centeredMonitorSpace,
    centeredMonitorStart,
} from '../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/taskbar/panelPositions.js';

const PANEL = 1920;
const LEFT = 100;
const RIGHT_IDLE = 500;
const RIGHT_RECORDING = 900;

function place(tlSize, brSize, size) {
    const available = centeredMonitorSpace(PANEL, tlSize, brSize, size);
    const fitted = Math.min(size, available);
    const start = centeredMonitorStart(0, PANEL, tlSize, brSize, fitted);
    return {available, fitted, start, end: start + fitted};
}

// Fits between the sides: centered on the monitor, as before.
const idle = place(LEFT, RIGHT_IDLE, 600);
assert.equal(idle.fitted, 600);
assert.equal(idle.start, (PANEL - 600) / 2);

// Recorder controls widen the right box: the symmetric space (120 px) would
// clip the icons, so the taskbar keeps its width and moves left of center.
const recording = place(LEFT, RIGHT_RECORDING, 600);
assert.equal(recording.fitted, 600);
assert.ok(recording.start < idle.start, 'taskbar moves left');
assert.ok(recording.start >= LEFT, 'left group is not overlapped');
assert.ok(recording.end <= PANEL - RIGHT_RECORDING, 'right group is not overlapped');

// Recording stops: the right box shrinks and the taskbar recenters.
assert.deepEqual(place(LEFT, RIGHT_IDLE, 600), idle);

// Mirrored case: a wide left side pushes the taskbar right.
const mirrored = place(RIGHT_RECORDING, LEFT, 600);
assert.ok(mirrored.start >= RIGHT_RECORDING);
assert.ok(mirrored.end <= PANEL - LEFT);

// Not even the free space is enough: fill it, starting after the left group.
const full = place(LEFT, RIGHT_RECORDING, 2000);
assert.equal(full.fitted, PANEL - LEFT - RIGHT_RECORDING);
assert.equal(full.start, LEFT);
assert.equal(full.end, PANEL - RIGHT_RECORDING);

console.log('taskbar center overflow scenarios passed');
