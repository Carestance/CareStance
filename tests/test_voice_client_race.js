const test = require('node:test');
const assert = require('node:assert');

// Mock browser globals for testing VoiceClient in Node environment
function setupMockBrowser() {
    global._mockAudioEl = {
        id: 'carestance-remote-audio',
        style: {},
        autoplay: false,
        playsInline: false,
        muted: false,
        volume: 1.0,
        srcObject: null,
        paused: true,
        play: () => {
            global._mockAudioEl.paused = false;
            return Promise.resolve();
        },
        pause: () => {
            global._mockAudioEl.paused = true;
        }
    };

    global.window = {};
    global.document = {
        getElementById: (id) => {
            if (id === 'carestance-remote-audio') {
                return global._mockAudioEl;
            }
            return null;
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

        async getStats() {
            return new Map([
                ['candidate-pair-1', {
                    id: 'candidate-pair-1',
                    type: 'candidate-pair',
                    state: 'succeeded',
                    nominated: true,
                    selected: true,
                    bytesSent: 100,
                    bytesReceived: 100,
                    packetsSent: 5,
                    packetsReceived: 5,
                    requestsSent: 1,
                    responsesReceived: 1,
                    requestsReceived: 1,
                    responsesSent: 1,
                    currentRoundTripTime: 0.05,
                    localCandidateId: 'local-1',
                    remoteCandidateId: 'remote-1'
                }],
                ['local-1', {
                    id: 'local-1',
                    type: 'local-candidate',
                    candidateType: 'host',
                    protocol: 'udp',
                    address: '127.0.0.1',
                    port: 50000
                }],
                ['remote-1', {
                    id: 'remote-1',
                    type: 'remote-candidate',
                    candidateType: 'host',
                    protocol: 'udp',
                    address: '127.0.0.1',
                    port: 50002
                }]
            ]);
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

test('VoiceClient Comprehensive Regression Test Suite', async (t) => {
    setupMockBrowser();
    const VoiceClient = require('../frontend/static/js/voice_client.js');

    // A. Normal connect
    await t.test('Scenario A: Normal connect lifecycle', async () => {
        global.fetch = async () => ({
            ok: true,
            status: 200,
            statusText: 'OK',
            json: async () => ({
                type: 'answer',
                sdp: 'v=0\nm=audio 5004 ...',
                session_id: 'session_normal_test'
            })
        });

        const stateChanges = [];
        const client = new VoiceClient('/api/webrtc/offer', (newState) => {
            stateChanges.push(newState);
        });

        await client.connect();

        assert.strictEqual(client.state, 'CONNECTING');
        assert.ok(stateChanges.includes('CONNECTING'), "Must emit CONNECTING state change");
        assert.ok(client.peerConnection, "PeerConnection must be created");
        assert.strictEqual(global.window.peerConnection, client.peerConnection, "window.peerConnection must be exposed");

        // Simulate connection established
        client.peerConnection.connectionState = 'connected';
        if (client.peerConnection.onconnectionstatechange) {
            await client.peerConnection.onconnectionstatechange();
        }
        assert.strictEqual(client.state, 'LISTENING', "State should transition to LISTENING when connected");

        // Check audio stream attachment
        const audioEl = global.document.getElementById('carestance-remote-audio');
        assert.ok(audioEl.srcObject, "Remote audio element must have stream attached");
        assert.strictEqual(audioEl._attachedAttemptId, client.connectionAttemptId);

        // Disconnect
        client.disconnect();
        assert.strictEqual(client.state, 'DISCONNECTED');
        assert.strictEqual(global.window.peerConnection, null, "window.peerConnection must be cleared after active disconnect");
        assert.strictEqual(audioEl.srcObject, null, "Audio element srcObject must be cleared after active disconnect");
    });

    // B. Disconnect/reconnect while fetch is pending
    await t.test('Scenario B: Disconnect/reconnect while fetch is pending', async () => {
        let delayedResolve;
        const delayedAnswerPromise = new Promise(resolve => {
            delayedResolve = resolve;
        });

        let callCount = 0;
        global.fetch = async () => {
            callCount++;
            if (callCount === 1) {
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
            }
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
        };

        const client1 = new VoiceClient('/api/webrtc/offer');
        const attempt1Promise = client1.connect();
        const initialAttempt1 = client1.connectionAttemptId;

        // Allow attempt 1 to proceed to in-flight fetch
        await new Promise(r => setTimeout(r, 20));

        // Start attempt 2 (reconnect)
        const client2 = new VoiceClient('/api/webrtc/offer');
        const attempt2Promise = client2.connect();
        await attempt2Promise;

        assert.strictEqual(VoiceClient.activeAttemptId, client2.connectionAttemptId);
        assert.strictEqual(VoiceClient.activeClient, client2);

        // Clean up delayed promise
        delayedResolve();
        await attempt1Promise;
    });

    // C. Stale answer after reconnect
    await t.test('Scenario C: Stale answer after reconnect arrives and is safely ignored', async () => {
        let delayedResolve;
        const delayedAnswerPromise = new Promise(resolve => {
            delayedResolve = resolve;
        });

        let callCount = 0;
        global.fetch = async () => {
            callCount++;
            if (callCount === 1) {
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
            }
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
        };

        const client1 = new VoiceClient('/api/webrtc/offer');
        const attempt1Promise = client1.connect();

        await new Promise(r => setTimeout(r, 20));

        const client2 = new VoiceClient('/api/webrtc/offer');
        await client2.connect();
        const pc2 = client2.peerConnection;

        // Deliver old answer for Attempt 1
        delayedResolve();

        // Must not reject or throw TypeError
        await assert.doesNotReject(
            attempt1Promise,
            "Old attempt must not throw when delayed answer arrives"
        );

        // Verify Attempt 2 remains untouched
        assert.strictEqual(VoiceClient.activeClient, client2);
        assert.strictEqual(client2.peerConnection, pc2);
        assert.strictEqual(global.document.getElementById('carestance-remote-audio')._attachedAttemptId, client2.connectionAttemptId);
    });

    // D. Stale disconnect cannot clear active audio
    await t.test('Scenario D: Stale disconnect cannot clear active audio element', async () => {
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

        // Stale client with arbitrary ID calls disconnect()
        const staleClient = new VoiceClient('/api/webrtc/offer');
        staleClient.connectionAttemptId = 99999;
        staleClient.disconnect();

        // Audio element must NOT be cleared by stale client
        assert.ok(audioEl.srcObject !== null, "Stale disconnect must NOT clear the active audio stream!");
        assert.strictEqual(audioEl._attachedAttemptId, activeClient.connectionAttemptId);

        // Active client disconnects cleanly
        activeClient.disconnect();
        assert.strictEqual(audioEl.srcObject, null, "Active client disconnect should cleanly clear the audio stream");
    });

    // E. Calling setState() from connect() never throws 'isCurrentAttempt is not a function'
    await t.test('Scenario E: isCurrentAttempt is defined on prototype and setState never throws', async () => {
        assert.strictEqual(typeof VoiceClient.prototype.isCurrentAttempt, 'function', "VoiceClient.prototype.isCurrentAttempt must be a function");
        assert.strictEqual(typeof VoiceClient.prototype.isValidPeerConnection, 'function', "VoiceClient.prototype.isValidPeerConnection must be a function");

        const client = new VoiceClient('/api/webrtc/offer');
        assert.strictEqual(typeof client.isCurrentAttempt, 'function', "client.isCurrentAttempt must be a function");
        assert.strictEqual(typeof client.isValidPeerConnection, 'function', "client.isValidPeerConnection must be a function");

        // Calling setState directly must not throw
        assert.doesNotThrow(() => {
            client.setState('CONNECTING');
        }, "setState('CONNECTING') must not throw");

        // Verify connect calls setState without throwing
        global.fetch = async () => ({
            ok: true,
            status: 200,
            statusText: 'OK',
            json: async () => ({
                type: 'answer',
                sdp: 'v=0\nm=audio ...',
                session_id: 'session_test_e'
            })
        });

        await assert.doesNotReject(
            client.connect(),
            "client.connect() must not reject with isCurrentAttempt is not a function"
        );
        client.disconnect();
    });

    // F. Rapid microphone clicks (duplicate initialization prevention)
    await t.test('Scenario F: Rapid microphone clicks (duplicate initialization prevention)', async () => {
        global.fetch = async () => ({
            ok: true,
            status: 200,
            statusText: 'OK',
            json: async () => ({
                type: 'answer',
                sdp: 'v=0\nm=audio ...',
                session_id: 'session_rapid_test'
            })
        });

        const client = new VoiceClient('/api/webrtc/offer');

        // Trigger 5 connect calls rapidly (simulating multiple clicks on kiosk)
        const p1 = client.connect();
        const p2 = client.connect();
        const p3 = client.connect();
        const p4 = client.connect();
        const p5 = client.connect();

        const initialAttemptId = client.connectionAttemptId;
        await Promise.all([p1, p2, p3, p4, p5]);

        // All calls should share the single attempt without incrementing connectionAttemptId 5 times
        assert.strictEqual(client.connectionAttemptId, initialAttemptId, "connectionAttemptId must remain the same across duplicate connect calls");
        client.disconnect();
    });

    // G. ICE failure collects final diagnostics and reports ICE_CONNECTION_FAILED
    await t.test('Scenario G: ICE failure collects final diagnostics and reports ICE_CONNECTION_FAILED', async () => {
        global.fetch = async () => ({
            ok: true,
            status: 200,
            statusText: 'OK',
            json: async () => ({
                type: 'answer',
                sdp: 'v=0\nm=audio ...',
                session_id: 'session_ice_fail_test'
            })
        });

        const messages = [];
        const client = new VoiceClient('/api/webrtc/offer', () => {}, (msg) => {
            messages.push(msg);
        });

        await client.connect();

        // Simulate ICE failure
        client.peerConnection.iceConnectionState = 'failed';
        client.peerConnection.connectionState = 'failed';
        if (client.peerConnection.oniceconnectionstatechange) {
            await client.peerConnection.oniceconnectionstatechange();
        }

        assert.strictEqual(client.state, 'ERROR', "State should transition to ERROR on ICE failure");
        assert.ok(messages.some(m => m.code === 'ICE_CONNECTION_FAILED'), "Must emit ICE_CONNECTION_FAILED error message");
        assert.strictEqual(global.window.peerConnection, null, "window.peerConnection must be cleaned up");
    });
});
