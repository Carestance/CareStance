const test = require('node:test');
const assert = require('node:assert');
const VoiceClient = require('../frontend/static/js/voice_client.js');

test('VoiceClient sends typed turns to the realtime data channel', () => {
    const client = new VoiceClient('/api/webrtc/offer');
    const sentMessages = [];
    client.dataChannel = {
        readyState: 'open',
        send: (message) => sentMessages.push(JSON.parse(message))
    };

    assert.strictEqual(client.sendText('  I like solving practical problems.  '), true);
    assert.deepStrictEqual(sentMessages, [{
        type: 'USER_TEXT',
        text: 'I like solving practical problems.'
    }]);
});

test('VoiceClient does not accept typed turns before the data channel is open', () => {
    const client = new VoiceClient('/api/webrtc/offer');
    let sendCount = 0;
    client.dataChannel = {
        readyState: 'connecting',
        send: () => { sendCount += 1; }
    };

    assert.strictEqual(client.sendText('A typed answer'), false);
    assert.strictEqual(client.sendText('   '), false);
    assert.strictEqual(sendCount, 0);
});
