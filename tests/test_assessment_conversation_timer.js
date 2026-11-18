const assert = require('node:assert/strict');
const test = require('node:test');
const {
    END_CHAT_DELAY_MS,
    createEndChatTimer,
    isEndChatAvailable
} = require('../frontend/static/js/assessment_conversation.js');

test('End Chat becomes available only at the five-minute boundary', () => {
    const startedAt = 1000;

    assert.equal(isEndChatAvailable(startedAt, startedAt + END_CHAT_DELAY_MS - 1), false);
    assert.equal(isEndChatAvailable(startedAt, startedAt + END_CHAT_DELAY_MS), true);
});

test('timer remains hidden until five minutes and resumes its stored start time', () => {
    const originalNow = Date.now;
    const originalStorage = global.sessionStorage;
    let now = 1000;
    const values = new Map();
    global.sessionStorage = {
        getItem: (key) => values.has(key) ? values.get(key) : null,
        setItem: (key, value) => values.set(key, value),
        removeItem: (key) => values.delete(key)
    };
    Date.now = () => now;

    const classes = new Set(['hidden']);
    const button = {
        hidden: true,
        classList: {
            toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name)
        }
    };
    const timer = createEndChatTimer(button, 'assessment-test');

    try {
        timer.start();
        assert.equal(button.hidden, true);

        now += END_CHAT_DELAY_MS - 1;
        timer.refresh();
        assert.equal(button.hidden, true);

        now += 1;
        timer.refresh();
        assert.equal(button.hidden, false);
        assert.equal(classes.has('hidden'), false);

        timer.clear();
        assert.equal(button.hidden, true);
        assert.equal(values.has('assessment-test'), false);

        values.set('assessment-test', String(now - END_CHAT_DELAY_MS));
        timer.resume();
        assert.equal(button.hidden, false);
    } finally {
        timer.clear();
        Date.now = originalNow;
        if (originalStorage === undefined) delete global.sessionStorage;
        else global.sessionStorage = originalStorage;
    }
});
