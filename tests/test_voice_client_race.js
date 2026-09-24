const test = require('node:test');
const assert = require('node:assert');

// Mock browser globals for testing VoiceClient in Node environment
function setupMockBrowser() {
    global.window = {};
    global.document = {
        getElementById: (id) => {
            if (!global._mockAudioEl) {
                global._mockAudioEl = {
                    id: 'carestance-remote-audio',
                    style: {},
                    autoplay: false,
                    playsInline: false,
                    muted: false,
                    volume: 1.0,
                    srcObject: null,
                    paused: true,
                    play: () => Promise.resolve(),
                    pause: () => { global._mockAudioEl.paused = true; }
                };
            }
            return global._mockAudioEl;
        },
        createElement: (tag) => {
            return {
                tagName: tag,
                id: '',
                style: {},
                play: () => Promise.resolve(),
                pause: () => {}
            };
        },
        body: {
            appendChild: () => {}
        },
        addEventListener: () => {},
        removeEventListener: () => {}
    };

    if (!global.navigator) {
        global.navigator = {};
    }
    Object.defineProperty(global.navigator, 'mediaDevices', {
        value: {
            getUserMedia: async () => ({
                getTracks: () => [{
                    kind: 'audio',
                    id: 'local_mic_track',
                    stop: () => {}
                }]
            })
        },
        configurable: true,
        writable: true
    });

    global.MediaStream = class MockMediaStream {
        constructor(tracks = []) {
            this.tracks = tracks;
        }
        getTracks() {
            return this.tracks;
        }
    };

    global.RTCSessionDescription = class MockRTCSessionDescription {
        constructor(init) {
            this.type = init.type;
            this.sdp = init.sdp;
        }
    };

    global.RTCPeerConnection = class MockRTCPeerConnection {
        constructor(config) {
            this.config = config;
            this.connectionState = 'new';
            this.iceConnectionState = 'new';
            this.signalingState = 'stable';
            this.iceGatheringState = 'complete';
            this.localDescription = { sdp: 'v=0\na=candidate:1 1 UDP ...', type: 'offer' };
            this.remoteDescription = null;
            this.tracks = [];
        }

        addTrack(track, stream) {
            this.tracks.push({ track, stream });
        }

        getTransceivers() {
            return [{
                sender: { track: { kind: 'audio' } },
                receiver: { track: { kind: 'audio' } },
                direction: 'sendrecv'
            }];
        }

        createDataChannel(label) {
            return {
                label,
                onmessage: null,
                send: () => {}
            };
        }

        async createOffer() {
            return { sdp: 'v=0\na=candidate:1 1 UDP ...', type: 'offer' };
        }

        async setLocalDescription(desc) {
            this.localDescription = desc;
        }

        async setRemoteDescription(desc) {
            if (this.signalingState === 'closed') {
                throw new Error("InvalidStateError: PeerConnection is closed");
            }
            this.remoteDescription = desc;
            this.signalingState = 'stable';
            // Simulate firing ontrack
            if (this.ontrack) {
                this.ontrack({
                    track: { kind: 'audio', id: 'remote_track_1', readyState: 'live', muted: false },
                    streams: [new global.MediaStream([{ kind: 'audio', id: 'remote_track_1' }])]
                });
            }
        }

        close() {
            this.signalingState = 'closed';
            this.connectionState = 'closed';
        }

        addEventListener(evt, handler) {
            if (evt === 'icegatheringstatechange') {
                // already complete
            }
        }

        removeEventListener() {}
    };
}

test('VoiceClient Race Condition Regression Test Suite', async (t) => {
    setupMockBrowser();
    const VoiceClient = require('../frontend/static/js/voice_client.js');

    await t.test('Scenario: connect -> await signaling -> disconnect/reconnect -> old SDP answer arrives', async () => {
        let delayedResolve;
        const delayedAnswerPromise = new Promise(resolve => {
            delayedResolve = resolve;
        });

        // Mock fetch: first call delays response, second call responds immediately
        let callCount = 0;
        global.fetch = async (url, options) => {
            callCount++;
            if (callCount === 1) {
                // Return delayed promise for attempt 1
                return delayedAnswerPromise.then(() => ({
                    ok: true,
                    status: 200,
                    statusText: 'OK',
                    json: async () => ({
                        type: 'answer',
                        sdp: 'v=0\nm=audio 5004 ...',
                        session_id: 'session_old_1'
                    })
                }));
            } else {
                // Immediate response for attempt 2
                return {
                    ok: true,
                    status: 200,
                    statusText: 'OK',
                    json: async () => ({
                        type: 'answer',
                        sdp: 'v=0\nm=audio 5006 ...',
                        session_id: 'session_new_2'
                    })
                };
            }
        };

        const client1 = new VoiceClient('/api/webrtc/offer');
        
        // 1. Start Attempt 1
        const attempt1Promise = client1.connect();
        assert.strictEqual(client1.connectionAttemptId, 1);
        assert.strictEqual(VoiceClient.activeAttemptId, 1);
        
        // Allow attempt 1 to proceed through getUserMedia, createOffer, setLocalDescription, and reach fetch()
        await new Promise(r => setTimeout(r, 50));
        const pc1 = client1.peerConnection;
        assert.ok(pc1, "Attempt 1 should have instantiated pc1");

        // 2. Disconnect and start Attempt 2 (reconnect) while attempt 1 fetch is still in flight
        const client2 = new VoiceClient('/api/webrtc/offer');
        const attempt2Promise = client2.connect();
        assert.strictEqual(client2.connectionAttemptId, 2);
        assert.strictEqual(VoiceClient.activeAttemptId, 2);

        // Wait for attempt 2 to complete its negotiation
        await attempt2Promise;
        const pc2 = client2.peerConnection;
        assert.ok(pc2, "Attempt 2 should have instantiated pc2");
        assert.notStrictEqual(pc1, pc2, "pc1 and pc2 must be distinct PeerConnections");
        assert.strictEqual(global.document.getElementById('carestance-remote-audio')._attachedAttemptId, 2);

        // 3. Now resolve the delayed SDP answer for Attempt 1
        // Expected: Attempt 1 must NOT throw TypeError: Cannot read properties of null (reading 'setRemoteDescription')
        // Expected: Attempt 1 must ignore the stale SDP answer
        // Expected: Attempt 2's pc2 and remoteAudio remain active!
        delayedResolve();

        // Await attempt 1 resolution
        await assert.doesNotReject(
            attempt1Promise,
            "Attempt 1 must not throw an unhandled error when old SDP answer arrives"
        );

        // 4. Verify Attempt 2 remains active and unaffected
        assert.strictEqual(VoiceClient.activeAttemptId, 2, "Active attempt ID must remain 2");
        assert.strictEqual(VoiceClient.activeClient, client2, "Active client must remain client2");
        assert.strictEqual(client2.peerConnection, pc2, "pc2 must remain the active peerConnection on client2");
        assert.strictEqual(pc2.signalingState, 'stable', "pc2 must have completed setRemoteDescription");
        assert.strictEqual(global.document.getElementById('carestance-remote-audio')._attachedAttemptId, 2, "Audio element must remain attached to attempt 2");
    });

    await t.test('Scenario: Stale disconnect does not clear active audio element', async () => {
        global.fetch = async () => ({
            ok: true,
            status: 200,
            statusText: 'OK',
            json: async () => ({
                type: 'answer',
                sdp: 'v=0\nm=audio ...',
                session_id: 'session_active'
            })
        });

        const activeClient = new VoiceClient('/api/webrtc/offer');
        await activeClient.connect();

        const audioEl = global.document.getElementById('carestance-remote-audio');
        assert.strictEqual(audioEl._attachedAttemptId, activeClient.connectionAttemptId);
        assert.ok(audioEl.srcObject, "Audio element must have an attached stream");

        // Simulate an old client attempt 999 calling disconnect()
        const staleClient = new VoiceClient('/api/webrtc/offer');
        staleClient.connectionAttemptId = 999; // Stale ID
        staleClient.disconnect();

        // Audio element must NOT be cleared by the stale client's disconnect!
        assert.ok(audioEl.srcObject !== null, "Stale disconnect must NOT clear the active audio stream!");
        assert.strictEqual(audioEl._attachedAttemptId, activeClient.connectionAttemptId);

        // Now active client disconnects
        activeClient.disconnect();
        assert.strictEqual(audioEl.srcObject, null, "Active client disconnect should cleanly clear the audio stream");
    });
});
