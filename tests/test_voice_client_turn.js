const test = require('node:test');
const assert = require('node:assert');

function setupMockBrowser(statsReportMap = null) {
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
        getElementById: (id) => (id === 'carestance-remote-audio' ? global._mockAudioEl : null),
        createElement: () => ({
            tagName: 'audio',
            style: {},
            play: () => Promise.resolve(),
            pause: () => {}
        }),
        body: { appendChild: () => {} },
        addEventListener: () => {},
        removeEventListener: () => {}
    };

    if (!global.navigator) {
        global.navigator = {};
    }
    Object.defineProperty(global.navigator, 'mediaDevices', {
        value: {
            getUserMedia: async () => ({
                getTracks: () => [{ kind: 'audio', id: 'mic_track', stop: () => {} }]
            })
        },
        configurable: true,
        writable: true
    });

    global.MediaStream = class MockMediaStream {
        constructor(tracks = []) { this.tracks = tracks; }
        getTracks() { return this.tracks; }
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
            this.localDescription = { sdp: 'v=0\na=candidate:1 1 UDP 2130706431 10.0.0.1 50000 typ host\na=candidate:2 1 UDP 16777215 152.55.1.1 60000 typ relay raddr 10.0.0.1 rport 50000', type: 'offer' };
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

        createDataChannel() {
            return { onmessage: null, send: () => {}, close: () => {} };
        }

        async createOffer() {
            return this.localDescription;
        }

        async setLocalDescription(desc) {
            this.localDescription = desc;
        }

        async setRemoteDescription(desc) {
            this.remoteDescription = desc;
            this.signalingState = 'stable';
            if (this.ontrack) {
                this.ontrack({
                    track: { kind: 'audio', id: 'remote_track_1', readyState: 'live', muted: false },
                    streams: [new global.MediaStream([{ kind: 'audio', id: 'remote_track_1' }])]
                });
            }
        }

        async getStats() {
            if (statsReportMap) return statsReportMap;
            return new Map([
                ['pair-relay', {
                    id: 'pair-relay',
                    type: 'candidate-pair',
                    state: 'succeeded',
                    nominated: true,
                    selected: true,
                    bytesSent: 500,
                    bytesReceived: 500,
                    requestsSent: 2,
                    responsesReceived: 2,
                    localCandidateId: 'local-relay',
                    remoteCandidateId: 'remote-relay'
                }],
                ['local-relay', {
                    id: 'local-relay',
                    type: 'local-candidate',
                    candidateType: 'relay',
                    protocol: 'udp',
                    address: '152.55.1.1',
                    port: 60000
                }],
                ['remote-relay', {
                    id: 'remote-relay',
                    type: 'remote-candidate',
                    candidateType: 'relay',
                    protocol: 'udp',
                    address: '152.55.1.2',
                    port: 60002
                }]
            ]);
        }

        close() {
            this.signalingState = 'closed';
            this.connectionState = 'closed';
        }

        addEventListener() {}
        removeEventListener() {}
    };
}

test('VoiceClient TURN Configuration & Relay Diagnostics', async (t) => {
    const VoiceClient = require('../frontend/static/js/voice_client.js');

    await t.test('1. Fetches and applies TURN ICE servers from /api/webrtc/config', async () => {
        setupMockBrowser();

        const mockIceServers = [
            { urls: ['stun:stun.l.google.com:19302'] },
            {
                urls: ['turn:turn.example.com:3478?transport=udp', 'turn:turn.example.com:3478?transport=tcp'],
                username: 'kiosk_user',
                credential: 'kiosk_password'
            }
        ];

        global.fetch = async (url) => {
            if (url && url.includes('/config')) {
                return {
                    ok: true,
                    status: 200,
                    json: async () => ({ iceServers: mockIceServers })
                };
            }
            return {
                ok: true,
                status: 200,
                json: async () => ({
                    type: 'answer',
                    sdp: 'v=0\na=candidate:... typ relay\nm=audio 5004 ...',
                    session_id: 'turn_test_session'
                })
            };
        };

        const client = new VoiceClient('/api/webrtc/offer');
        await client.connect();

        assert.ok(client.peerConnection, 'PeerConnection must be created');
        assert.deepStrictEqual(
            client.peerConnection.config.iceServers,
            mockIceServers,
            'RTCPeerConnection must receive the TURN iceServers from /config'
        );
        client.disconnect();
    });

    await t.test('2. Missing or failed /api/webrtc/config gracefully falls back to default STUN', async () => {
        setupMockBrowser();

        global.fetch = async (url) => {
            if (url && url.includes('/config')) {
                return {
                    ok: false,
                    status: 404,
                    statusText: 'Not Found'
                };
            }
            return {
                ok: true,
                status: 200,
                json: async () => ({
                    type: 'answer',
                    sdp: 'v=0\nm=audio 5004 ...',
                    session_id: 'turn_test_session_fallback'
                })
            };
        };

        const client = new VoiceClient('/api/webrtc/offer');
        await client.connect();

        assert.ok(client.peerConnection, 'PeerConnection must be created even if config fails');
        assert.ok(
            client.peerConnection.config.iceServers.length >= 1,
            'Must contain fallback STUN servers'
        );
        assert.ok(
            client.peerConnection.config.iceServers[0].urls[0].includes('stun'),
            'Fallback must be STUN'
        );
        client.disconnect();
    });

    await t.test('3. Detects relay candidates and logs TURN candidate detected and selected pair', async () => {
        setupMockBrowser();

        const logs = [];
        const client = new VoiceClient('/api/webrtc/offer');
        client.log = (...args) => logs.push(args.join(' '));

        global.fetch = async (url) => {
            if (url && url.includes('/config')) {
                return {
                    ok: true,
                    status: 200,
                    json: async () => ({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
                };
            }
            return {
                ok: true,
                status: 200,
                json: async () => ({
                    type: 'answer',
                    sdp: 'v=0\nm=audio 5004 ...',
                    session_id: 'turn_test_session_diag'
                })
            };
        };

        await client.connect();

        const diag = await client.collectIceDiagnostics(client.peerConnection, 1, 'TEST RELAY DIAGNOSTICS');
        assert.ok(diag, 'Diagnostics object must be collected');

        // Check relay candidate logs
        const turnDetectedLogs = logs.filter(l => l.includes('TURN candidate detected'));
        assert.ok(turnDetectedLogs.length >= 2, 'Must log local and remote relay candidates');
        assert.ok(turnDetectedLogs.some(l => l.includes('local-candidate') && l.includes('candidateType=relay')));
        assert.ok(turnDetectedLogs.some(l => l.includes('remote-candidate') && l.includes('candidateType=relay')));

        // Check selected pair logs
        const selectedPairLog = logs.find(l => l.includes('Selected ICE Pair'));
        assert.ok(selectedPairLog, 'Must log selected ICE pair');
        assert.ok(selectedPairLog.includes('localType=relay'), 'Selected pair localType must be relay');
        assert.ok(selectedPairLog.includes('remoteType=relay'), 'Selected pair remoteType must be relay');

        client.disconnect();
    });
});
