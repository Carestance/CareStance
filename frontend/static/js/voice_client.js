/**
 * VoiceClient - WebRTC Conversational AI Client for CareStance.
 * Robust, singleton-managed WebRTC lifecycle with structured logging,
 * full ICE candidate gathering, autoplay handling, and inbound RTP metrics.
 */
class VoiceClient {
    constructor(wsUrl, onStateChange, onMessage) {
        // The offer exchange is HTTP even though older callers pass a WebSocket URL.
        this.apiUrl = this.resolveApiUrl(wsUrl);
        this.onStateChange = onStateChange || function() {};
        this.onMessage = onMessage || function() {};
        
        this.state = 'IDLE';
        this.peerConnection = null;
        this.localStream = null;
        this.dataChannel = null;
        this.abortController = null;
        this.sessionId = null;
        this.statsInterval = null;
        this.debug = true; // Structured WebRTC logging enabled

        // Concurrency and lifecycle tracking
        this.currentAttemptId = 0;
        this.isConnecting = false;
        this.isDisconnecting = false;
        this.chatHistory = [];

        // Client ID persistence
        this.clientId = localStorage.getItem('carestance_client_id');
        if (!this.clientId) {
            this.clientId = 'client_' + Math.random().toString(36).substring(2, 11);
            localStorage.setItem('carestance_client_id', this.clientId);
        }

        // Initialize or bind to the hidden remote audio element
        this.initAudioElement();

        // Register on window for accessibility
        window.voiceClient = this;
    }

    log(...args) {
        if (this.debug) {
            console.log(...args);
        }
    }

    logAudioState(prefix = "[WebRTC] Audio element state:") {
        if (!this.remoteAudio) return;
        this.log(prefix, {
            srcObject: !!this.remoteAudio.srcObject,
            streamTracks: this.remoteAudio.srcObject ? this.remoteAudio.srcObject.getTracks().map(t => ({
                id: t.id,
                kind: t.kind,
                readyState: t.readyState,
                muted: t.muted
            })) : [],
            paused: this.remoteAudio.paused,
            muted: this.remoteAudio.muted,
            volume: this.remoteAudio.volume,
            readyState: this.remoteAudio.readyState,
            networkState: this.remoteAudio.networkState
        });
    }

    initAudioElement() {
        let el = document.getElementById('carestance-remote-audio');
        if (!el) {
            el = document.createElement('audio');
            el.id = 'carestance-remote-audio';
            // Do NOT use display: none; some kiosk browsers throttle or disable audio on display:none elements
            el.style.position = 'fixed';
            el.style.left = '-9999px';
            el.style.top = '-9999px';
            el.style.width = '1px';
            el.style.height = '1px';
            el.style.opacity = '0.01';
            el.style.pointerEvents = 'none';
            document.body.appendChild(el);
        }
        
        el.autoplay = true;
        el.playsInline = true;
        el.muted = false;
        el.volume = 1.0;
        
        this.remoteAudio = el;
    }

    resolveApiUrl(url) {
        if (!url) return '/api/webrtc/offer';
        return url.replace(/^ws:/, 'http:').replace(/^wss:/, 'https:');
    }

    setState(newState) {
        if (this.state === newState) return;
        this.state = newState;
        if (typeof this.onStateChange === 'function') {
            try {
                this.onStateChange(newState);
            } catch (err) {
                console.error("[VoiceClient] onStateChange error:", err);
            }
        }
    }

    /**
     * Unlocks audio context and elements during an explicit user interaction (click/touch).
     */
    unlockAudio() {
        if (this.remoteAudio) {
            this.remoteAudio.muted = false;
            this.remoteAudio.volume = 1.0;
        }

        // Web Audio Context unlock
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) {
                if (!this.audioCtx) {
                    this.audioCtx = new AudioCtx();
                }
                if (this.audioCtx.state === 'suspended') {
                    this.audioCtx.resume().catch(() => {});
                }
            }
        } catch (e) {
            this.log("[WebRTC] AudioContext unlock exception:", e);
        }
    }

    waitForIceGathering(peerConnection, timeoutMs = 5000) {
        if (peerConnection.iceGatheringState === 'complete') {
            return Promise.resolve();
        }

        return new Promise(resolve => {
            let settled = false;
            const finish = () => {
                if (settled) return;
                settled = true;
                clearTimeout(timeoutId);
                peerConnection.removeEventListener('icegatheringstatechange', onStateChange);
                resolve();
            };
            const onStateChange = () => {
                if (peerConnection.iceGatheringState === 'complete') finish();
            };
            const timeoutId = setTimeout(finish, timeoutMs);
            peerConnection.addEventListener('icegatheringstatechange', onStateChange);
        });
    }

    async connect() {
        // Prevent duplicate concurrent initialization
        if (this.isConnecting || this.state === 'CONNECTING' || this.state === 'LISTENING' || this.state === 'SPEAKING') {
            this.log("[WebRTC] duplicate initialization ignored; current state:", this.state);
            return;
        }

        // Assign unique attempt ID to invalidate any stale concurrent/previous runs
        const attemptId = ++this.currentAttemptId;
        this.isConnecting = true;
        this.isDisconnecting = false;
        this.setState('CONNECTING');

        // Prime audio within the user gesture chain
        this.unlockAudio();

        try {
            if (!window.isSecureContext && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
                throw new Error('Microphone access requires HTTPS.');
            }
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error('This browser does not support microphone access.');
            }
            this.abortController = new AbortController();

            // 1. Get user media (microphone)
            this.log("[WebRTC] Requesting microphone access");
            try {
                this.localStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    },
                    video: false
                });
            } catch (mediaError) {
                if (mediaError.name === 'NotAllowedError') {
                    console.error("[WebRTC] Microphone access denied by user (NotAllowedError)");
                } else {
                    console.error("[WebRTC] Failed to access microphone:", mediaError);
                }
                throw mediaError;
            }

            // Initialize WebRTC Peer Connection with STUN servers
            const peerConnection = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' },
                    { urls: 'stun:stun2.l.google.com:19302' }
                ]
            });
            this.peerConnection = peerConnection;

            // 3. Add local tracks to peer connection
            this.localStream.getTracks().forEach(track => {
                peerConnection.addTrack(track, this.localStream);
            });

            // Ensure audio transceiver direction is sendrecv
            const transceivers = pc.getTransceivers ? pc.getTransceivers() : [];
            const audioTransceiver = transceivers.find(t => 
                (t.sender && t.sender.track && t.sender.track.kind === 'audio') ||
                (t.receiver && t.receiver.track && t.receiver.track.kind === 'audio')
            );
            if (audioTransceiver) {
                audioTransceiver.direction = 'sendrecv';
            }

            // 4. Create Data Channel for Pipecat transcripts & events
            this.dataChannel = pc.createDataChannel("pipecat");
            this.dataChannel.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    this.onMessage(msg);
                } catch (e) {
                    this.log("[VoiceClient] Data channel message (non-JSON):", event.data);
                }
            };

            // Handle incoming remote audio stream & apply volume gain boost
            peerConnection.ontrack = (event) => {
                if (event.streams && event.streams[0]) {
                    this.remoteAudio.srcObject = event.streams[0];
                    
                    try {
                        const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
                        if (AudioCtxClass && !this.audioCtx) {
                            this.audioCtx = new AudioCtxClass();
                            const source = this.audioCtx.createMediaStreamSource(event.streams[0]);
                            const gainNode = this.audioCtx.createGain();
                            gainNode.gain.value = 1.5;
                            source.connect(gainNode);
                            gainNode.connect(this.audioCtx.destination);
                            if (this.audioCtx.state === 'suspended') {
                                this.audioCtx.resume();
                            }
                            // Mute raw HTML audio element to prevent double-output acoustic echo
                            this.remoteAudio.muted = true;
                        }
                    } catch (gainErr) {
                        console.warn("Volume gain boost note:", gainErr);
                        this.remoteAudio.muted = false;
                        this.remoteAudio.volume = 1.0;
                    }
                    
                    this.remoteAudio.play().catch(() => {});
                }

                // Track event listeners
                event.track.onended = () => {
                    this.log("[WebRTC] Remote track ended:", event.track.id);
                };
                event.track.onmute = () => {
                    this.log("[WebRTC] Remote track muted:", event.track.id);
                };
                event.track.onunmute = () => {
                    this.log("[WebRTC] Remote track unmuted:", event.track.id);
                };
            };

            peerConnection.onconnectionstatechange = () => {
                if (peerConnection.connectionState === 'connected') {
                    this.setState('LISTENING');
                } else if (peerConnection.connectionState === 'disconnected' ||
                           peerConnection.connectionState === 'failed') {
                    this.disconnect();
                }
            };

            // Create WebRTC Offer
            const offer = await peerConnection.createOffer();
            await peerConnection.setLocalDescription(offer);
            // Send a complete SDP so the server can establish the connection without
            // relying on trickle ICE candidates that this endpoint does not exchange.
            await this.waitForIceGathering(peerConnection);

            // Check if aborted while gathering ICE
            if (this.currentAttemptId !== attemptId || this.isDisconnecting) {
                this.log("[WebRTC] Stale connection attempt aborted during ICE gathering");
                return;
            }

            // 9. Send Offer to Backend
            this.log("[WebRTC] Sending offer");
            const response = await fetch(this.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': this.clientId
                },
                credentials: 'include',
                signal: this.abortController.signal,
                body: JSON.stringify({
                    sdp: peerConnection.localDescription.sdp,
                    type: peerConnection.localDescription.type
                })
            });

            if (!response.ok) {
                throw new Error(`Failed SDP negotiation: ${response.status} ${response.statusText}`);
            }

            const answerData = await response.json();
            this.log("[WebRTC] Received SDP answer");

            // Check if aborted while waiting for backend response
            if (this.currentAttemptId !== attemptId || this.isDisconnecting) {
                this.log("[WebRTC] Stale connection attempt aborted during SDP answer fetch");
                return;
            }

            // 10. Set Remote Description (Answer)
            this.log("[WebRTC] Setting remote description");
            await pc.setRemoteDescription(new RTCSessionDescription({
                sdp: answerData.sdp,
                type: answerData.type
            }));

            if (answerData.session_id) {
                this.sessionId = answerData.session_id;
            }

        } catch (error) {
            console.error("WebRTC Connection failed:", error);
            this.onMessage({
                type: 'VOICE_ERROR',
                code: error.name || 'VOICE_CONNECTION_FAILED',
                message: error.message || 'Unable to access the microphone.'
            });
            this.disconnect('ERROR');
        } finally {
            if (this.currentAttemptId === attemptId) {
                this.isConnecting = false;
            }
        }
    }

    /**
     * Inspects inbound audio RTP statistics from WebRTC internals.
     * Helps differentiate between:
     * (a) RTP packets not arriving from server vs
     * (b) RTP packets arriving but browser audio element not playing.
     */
    async getInboundRtpStats() {
        if (!this.peerConnection) return null;
        try {
            const statsReport = await this.peerConnection.getStats();
            let inboundAudio = null;
            statsReport.forEach(report => {
                if (report.type === 'inbound-rtp' && (report.kind === 'audio' || report.mediaType === 'audio')) {
                    inboundAudio = {
                        packetsReceived: report.packetsReceived || 0,
                        bytesReceived: report.bytesReceived || 0,
                        packetsLost: report.packetsLost || 0,
                        jitter: report.jitter !== undefined ? report.jitter : null,
                        audioLevel: report.audioLevel !== undefined ? report.audioLevel : null,
                        timestamp: report.timestamp
                    };
                }
            });
            return inboundAudio;
        } catch (e) {
            this.log("[WebRTC] Failed to collect inbound RTP stats:", e);
            return null;
        }
    }

    startStatsMonitoring(intervalMs = 2500) {
        this.stopStatsMonitoring();
        this.statsInterval = setInterval(async () => {
            if (!this.peerConnection || this.peerConnection.connectionState !== 'connected') {
                return;
            }
            const rtp = await this.getInboundRtpStats();
            if (rtp) {
                this.log(`[WebRTC] Inbound RTP stats: packetsReceived=${rtp.packetsReceived}, bytesReceived=${rtp.bytesReceived}, packetsLost=${rtp.packetsLost}, jitter=${rtp.jitter}, audioLevel=${rtp.audioLevel}`);
            }
        }, intervalMs);
    }

    stopStatsMonitoring() {
        if (this.statsInterval) {
            clearInterval(this.statsInterval);
            this.statsInterval = null;
        }
    }

    async handleUserSpeech(text) {
        if (!text) return;
        this.onMessage(text, 'user');
        this.chatHistory.push({ role: 'user', content: text });
    }

    speak(text) {
        this.onMessage(text, 'assistant');
        this.setState('SPEAKING');
    }

    disconnect(nextState = 'DISCONNECTED') {
        this.isDisconnecting = true;
        this.isConnecting = false;
        // Invalidate in-flight connect attempts
        this.currentAttemptId++;

        this.stopStatsMonitoring();

        // Abort in-flight HTTP offer request
        if (this.abortController) {
            try {
                this.abortController.abort();
            } catch (e) {}
            this.abortController = null;
        }

        // Close peer connection cleanly
        if (this.peerConnection) {
            this.log("[WebRTC] Closing PeerConnection");
            try {
                this.peerConnection.ontrack = null;
                this.peerConnection.oniceconnectionstatechange = null;
                this.peerConnection.onconnectionstatechange = null;
                this.peerConnection.onsignalingstatechange = null;
                this.peerConnection.close();
            } catch (e) {
                console.error("[WebRTC] Error closing peerConnection:", e);
            }
            this.peerConnection = null;
            if (window.peerConnection === this.peerConnection) {
                window.peerConnection = null;
            }
        }

        // Stop microphone stream tracks
        if (this.localStream) {
            try {
                this.localStream.getTracks().forEach(track => track.stop());
            } catch (e) {}
            this.localStream = null;
        }

        // Clean up remote audio element
        if (this.remoteAudio) {
            try {
                this.remoteAudio.pause();
                this.remoteAudio.srcObject = null;
            } catch (e) {}
        }

        this.setState(nextState);
    }
}

// Global export for browser script usage
window.VoiceClient = VoiceClient;
