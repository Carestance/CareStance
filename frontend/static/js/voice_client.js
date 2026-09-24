/**
 * VoiceClient - WebRTC Conversational AI Client for CareStance.
 * Single-active-connection lifecycle with epoch tracking, non-trickle ICE
 * synchronization, audio element protection, and inbound RTP metrics.
 */
class VoiceClient {
    // Static attempt tracking to guarantee single-active-connection semantics
    static globalAttemptCounter = 0;
    static activeAttemptId = 0;
    static activeClient = null;

    constructor(wsUrl, onStateChange, onMessage) {
        // wsUrl is repurposed as the API endpoint for WebRTC offer exchange if provided,
        // otherwise it defaults to the /api/webrtc/offer endpoint.
        this.apiUrl = wsUrl ? wsUrl.replace("ws://", "http://").replace("wss://", "https://") : '/api/webrtc/offer';
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

        // Internal attempt tracking
        this.connectionAttemptId = 0;
        this.isConnecting = false;
        this.isDisconnecting = false;
        this.chatHistory = [];

        // Client ID persistence
        if (typeof localStorage !== 'undefined') {
            this.clientId = localStorage.getItem('carestance_client_id');
            if (!this.clientId) {
                this.clientId = 'client_' + Math.random().toString(36).substring(2, 11);
                localStorage.setItem('carestance_client_id', this.clientId);
            }
        } else {
            this.clientId = 'client_node_' + Math.random().toString(36).substring(2, 11);
        }

        // Initialize or bind to the hidden remote audio element
        this.initAudioElement();
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
        if (typeof document === 'undefined') return;

        let el = document.getElementById('carestance-remote-audio');
        if (!el) {
            el = document.createElement('audio');
            el.id = 'carestance-remote-audio';
            // Rendered off-screen so browser media engine treats element as active
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

    /**
     * Determines whether a given attempt ID currently represents the active connection attempt.
     */
    isCurrentAttempt(attemptId = this.connectionAttemptId) {
        return (
            attemptId > 0 &&
            attemptId === this.connectionAttemptId &&
            this.connectionAttemptId === VoiceClient.activeAttemptId &&
            !this.isDisconnecting
        );
    }

    /**
     * Validates that the captured PeerConnection instance is still the active connection,
     * matches the current attempt, and has not been closed or replaced.
     */
    isValidPeerConnection(pc, attemptId = this.connectionAttemptId) {
        if (!this.isCurrentAttempt(attemptId)) {
            this.log(`[WebRTC] [Attempt #${attemptId}] Validation failed: attempt is stale (current active: #${VoiceClient.activeAttemptId}, isDisconnecting=${this.isDisconnecting})`);
            return false;
        }
        if (!pc) {
            this.log(`[WebRTC] [Attempt #${attemptId}] Validation failed: captured pc is null/undefined`);
            return false;
        }
        if (this.peerConnection !== pc) {
            this.log(`[WebRTC] [Attempt #${attemptId}] Validation failed: PeerConnection reference changed (active PC !== captured PC)`);
            return false;
        }
        if (pc.signalingState === "closed") {
            this.log(`[WebRTC] [Attempt #${attemptId}] Validation failed: pc.signalingState is "closed"`);
            return false;
        }
        return true;
    }

    setState(newState) {
        if (!this.isCurrentAttempt() && newState !== 'DISCONNECTED') {
            this.log(`[WebRTC] Ignoring setState('${newState}') for stale attempt ${this.connectionAttemptId}`);
            return;
        }
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
     * Fallback autoplay unlock handler if browser policy prevents initial play.
     */
    setupAutoplayUnlock() {
        if (typeof document === 'undefined') return;

        this.log("[WebRTC] Registering user-interaction fallback for audio unlock");
        const unlock = () => {
            if (this.isCurrentAttempt() && this.remoteAudio && this.remoteAudio.srcObject) {
                this.remoteAudio.muted = false;
                this.remoteAudio.volume = 1.0;
                this.remoteAudio.play().then(() => {
                    this.log("[WebRTC] Audio playback started (via user gesture unlock)");
                }).catch((err) => {
                    console.warn("[WebRTC] User-gesture audio unlock failed:", err);
                });
            }
            document.removeEventListener('click', unlock, true);
            document.removeEventListener('touchstart', unlock, true);
            document.removeEventListener('keydown', unlock, true);
        };

        document.addEventListener('click', unlock, true);
        document.addEventListener('touchstart', unlock, true);
        document.addEventListener('keydown', unlock, true);
    }

    /**
     * Waits for non-trickle ICE gathering to complete before sending SDP offer.
     */
    waitForIceGatheringComplete(pc, timeoutMs = 2000) {
        this.log("[WebRTC] ICE gathering started");
        return new Promise((resolve) => {
            if (pc.iceGatheringState === 'complete') {
                this.log("[WebRTC] ICE gathering state: complete");
                resolve();
                return;
            }

            this.log(`[WebRTC] ICE gathering state: ${pc.iceGatheringState}`);
            let timer = null;

            const onStateChange = () => {
                this.log(`[WebRTC] ICE gathering state: ${pc.iceGatheringState}`);
                if (pc.iceGatheringState === 'complete') {
                    cleanup();
                    resolve();
                }
            };

            const cleanup = () => {
                if (timer) clearTimeout(timer);
                pc.removeEventListener('icegatheringstatechange', onStateChange);
            };

            pc.addEventListener('icegatheringstatechange', onStateChange);

            timer = setTimeout(() => {
                this.log("[WebRTC] ICE gathering timeout reached (proceeding with gathered candidates)");
                cleanup();
                resolve();
            }, timeoutMs);
        });
    }

    async connect() {
        // Prevent duplicate concurrent initialization
        if (this.isConnecting || this.state === 'CONNECTING' || this.state === 'LISTENING' || this.state === 'CONNECTED' || this.state === 'SPEAKING') {
            this.log("[WebRTC] duplicate initialization ignored; current state:", this.state);
            return;
        }

        // Cleanly disconnect any previous global active instance before starting new
        if (VoiceClient.activeClient && VoiceClient.activeClient !== this) {
            this.log("[WebRTC] Disconnecting previous active client instance");
            try {
                VoiceClient.activeClient.disconnect();
            } catch (e) {}
        }

        // Assign unique attempt ID to invalidate any stale concurrent/previous runs
        const attemptId = ++VoiceClient.globalAttemptCounter;
        this.connectionAttemptId = attemptId;
        VoiceClient.activeAttemptId = attemptId;
        VoiceClient.activeClient = this;

        this.isConnecting = true;
        this.isDisconnecting = false;
        this.setState('CONNECTING');

        // Expose globally for diagnostics and kiosk telemetry
        if (typeof window !== 'undefined') {
            window.voiceClient = this;
        }

        try {
            // Cancel any prior in-flight fetch request
            if (this.abortController) {
                this.abortController.abort();
            }
            this.abortController = new AbortController();

            // 1. Get user media (microphone)
            this.log(`[WebRTC] [Attempt #${attemptId}] Requesting microphone access`);
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

            // Check if connection was aborted while waiting for mic permission
            if (!this.isCurrentAttempt(attemptId)) {
                this.log(`[WebRTC] [Attempt #${attemptId}] Stale PeerConnection attempt after getUserMedia aborted; stopping local tracks`);
                if (this.localStream) {
                    this.localStream.getTracks().forEach(t => t.stop());
                    this.localStream = null;
                }
                return;
            }

            // 2. Create RTCPeerConnection
            this.log(`[WebRTC] [Attempt #${attemptId}] Creating PeerConnection`);
            const pc = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' },
                    { urls: 'stun:stun2.l.google.com:19302' }
                ]
            });
            this.peerConnection = pc;
            if (typeof window !== 'undefined') {
                window.peerConnection = pc;
            }

            // 3. Add local tracks to peer connection
            this.localStream.getTracks().forEach(track => {
                pc.addTrack(track, this.localStream);
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
                if (!this.isValidPeerConnection(pc, attemptId)) return;
                try {
                    const msg = JSON.parse(event.data);
                    this.onMessage(msg);
                } catch (e) {
                    this.log("[VoiceClient] Data channel message (non-JSON):", event.data);
                }
            };

            // 5. Handle remote audio track & play directly through audio element
            pc.ontrack = (event) => {
                if (!this.isValidPeerConnection(pc, attemptId)) {
                    this.log(`[WebRTC] [Attempt #${attemptId}] Stale track event ignored`);
                    return;
                }

                if (event.track.kind !== "audio") {
                    this.log(`[WebRTC] [Attempt #${attemptId}] Remote track received (ignored non-audio):`, event.track.kind);
                    return;
                }

                this.log(`[WebRTC] [Attempt #${attemptId}] Remote track received`, {
                    kind: event.track.kind,
                    id: event.track.id,
                    readyState: event.track.readyState,
                    muted: event.track.muted,
                    streamId: (event.streams && event.streams[0]) ? event.streams[0].id : "new"
                });

                const stream = (event.streams && event.streams[0]) 
                    ? event.streams[0] 
                    : new MediaStream([event.track]);

                if (this.remoteAudio) {
                    this.remoteAudio.srcObject = stream;
                    this.remoteAudio.muted = false;
                    this.remoteAudio.volume = 1.0;
                    this.remoteAudio.autoplay = true;
                    this.remoteAudio.playsInline = true;
                    this.remoteAudio._attachedAttemptId = attemptId;

                    this.log(`[WebRTC] [Attempt #${attemptId}] Remote audio stream attached`);
                    this.logAudioState();

                    const playPromise = this.remoteAudio.play();
                    if (playPromise !== undefined) {
                        playPromise.then(() => {
                            this.log(`[WebRTC] [Attempt #${attemptId}] Audio playback started`);
                            this.logAudioState();
                        }).catch((error) => {
                            console.error(`[WebRTC] [Attempt #${attemptId}] Audio playback failed:`, error);
                            this.logAudioState();
                            if (error.name === "NotAllowedError") {
                                this.setupAutoplayUnlock();
                            }
                        });
                    }
                }

                event.track.onended = () => {
                    this.log(`[WebRTC] [Attempt #${attemptId}] Remote track ended:`, event.track.id);
                };
                event.track.onmute = () => {
                    this.log(`[WebRTC] [Attempt #${attemptId}] Remote track muted:`, event.track.id);
                };
                event.track.onunmute = () => {
                    this.log(`[WebRTC] [Attempt #${attemptId}] Remote track unmuted:`, event.track.id);
                };
            };

            // 6. Monitor connection, ICE, and signaling states
            pc.onconnectionstatechange = () => {
                if (!this.isValidPeerConnection(pc, attemptId)) {
                    this.log(`[WebRTC] [Attempt #${attemptId}] Stale connectionstatechange ignored (state=${pc ? pc.connectionState : 'null'})`);
                    return;
                }
                const cState = pc.connectionState;
                this.log(`[WebRTC] [Attempt #${attemptId}] connectionState=${cState}`);
                
                if (cState === 'connected') {
                    this.setState('LISTENING');
                    this.startStatsMonitoring();
                } else if (cState === 'disconnected' || cState === 'failed') {
                    console.warn(`[WebRTC] [Attempt #${attemptId}] Connection state changed to ${cState}`);
                    this.disconnect();
                }
            };

            pc.oniceconnectionstatechange = () => {
                if (!this.isValidPeerConnection(pc, attemptId)) return;
                const iceState = pc.iceConnectionState;
                this.log(`[WebRTC] [Attempt #${attemptId}] iceConnectionState=${iceState}`);
                if (iceState === 'failed') {
                    console.error(`[WebRTC] [Attempt #${attemptId}] ICE failure detected`);
                    this.disconnect();
                }
            };

            pc.onsignalingstatechange = () => {
                if (!this.isValidPeerConnection(pc, attemptId)) return;
                const sigState = pc.signalingState;
                this.log(`[WebRTC] [Attempt #${attemptId}] signalingState=${sigState}`);
            };

            // 7. Create WebRTC Offer
            this.log(`[WebRTC] [Attempt #${attemptId}] Creating offer`);
            const offer = await pc.createOffer();
            if (!this.isValidPeerConnection(pc, attemptId)) {
                this.log(`[WebRTC] [Attempt #${attemptId}] Aborted after createOffer; PeerConnection reference changed or closed`);
                return;
            }

            // 8. Set Local Description
            this.log(`[WebRTC] [Attempt #${attemptId}] Setting local description`);
            await pc.setLocalDescription(offer);
            if (!this.isValidPeerConnection(pc, attemptId)) {
                this.log(`[WebRTC] [Attempt #${attemptId}] Aborted after setLocalDescription; PeerConnection reference changed or closed`);
                return;
            }

            // 9. Wait for ICE gathering to complete before sending SDP offer (Vanilla ICE)
            await this.waitForIceGatheringComplete(pc, 2000);
            if (!this.isValidPeerConnection(pc, attemptId)) {
                this.log(`[WebRTC] [Attempt #${attemptId}] Aborted after ICE gathering wait; PeerConnection reference changed or closed`);
                return;
            }

            // 10. Inspect candidate presence and send offer
            const hasCandidates = pc.localDescription && pc.localDescription.sdp.includes("a=candidate:");
            this.log(`[WebRTC] [Attempt #${attemptId}] SDP contains candidates: ${hasCandidates}`);
            this.log(`[WebRTC] [Attempt #${attemptId}] Sending fully gathered SDP offer`);

            const response = await fetch(this.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': this.clientId
                },
                credentials: 'include',
                signal: this.abortController.signal,
                body: JSON.stringify({
                    sdp: pc.localDescription.sdp,
                    type: pc.localDescription.type
                })
            });

            if (!this.isValidPeerConnection(pc, attemptId)) {
                this.log(`[WebRTC] [Attempt #${attemptId}] Aborted after fetch response received; PeerConnection reference changed or closed`);
                return;
            }

            if (!response.ok) {
                throw new Error(`Failed SDP negotiation: ${response.status} ${response.statusText}`);
            }

            const answerData = await response.json();
            this.log(`[WebRTC] [Attempt #${attemptId}] Received SDP answer`);

            // 11. Validate attempt and PeerConnection reference immediately before setRemoteDescription
            if (!this.isCurrentAttempt(attemptId)) {
                console.warn(`[VoiceClient] [Attempt #${attemptId}] Stale attempt; ignoring SDP answer`);
                return;
            }

            if (!pc || this.peerConnection !== pc || pc.signalingState === "closed") {
                console.warn(`[VoiceClient] [Attempt #${attemptId}] PeerConnection is no longer active (pc=${!!pc}, activeMatches=${this.peerConnection === pc}, signalingState=${pc ? pc.signalingState : 'null'}); ignoring SDP answer`);
                return;
            }

            // 12. Set Remote Description (Answer) using captured pc reference
            this.log(`[WebRTC] [Attempt #${attemptId}] Setting remote description`);
            await pc.setRemoteDescription(new RTCSessionDescription({
                sdp: answerData.sdp,
                type: answerData.type || "answer"
            }));

            if (!this.isValidPeerConnection(pc, attemptId)) {
                this.log(`[WebRTC] [Attempt #${attemptId}] Aborted after setRemoteDescription; PeerConnection reference changed or closed`);
                return;
            }

            if (answerData.session_id) {
                this.sessionId = answerData.session_id;
            }

        } catch (error) {
            // Handle AbortError separately so it is not reported as a genuine WebRTC failure
            if (error.name === 'AbortError') {
                this.log(`[WebRTC] [Attempt #${attemptId}] Network request cancelled via AbortController`);
                return;
            }

            console.error(`[WebRTC] [Attempt #${attemptId}] WebRTC Connection failed:`, error);
            if (this.isCurrentAttempt(attemptId)) {
                this.setState('ERROR');
                this.disconnect();
            }
        } finally {
            if (this.connectionAttemptId === attemptId) {
                this.isConnecting = false;
            }
        }
    }

    /**
     * Inspects inbound audio RTP statistics from WebRTC internals.
     */
    async getInboundAudioStats() {
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
            this.log("[WebRTC] Failed to collect inbound audio stats:", e);
            return null;
        }
    }

    getInboundRtpStats() {
        return this.getInboundAudioStats();
    }

    startStatsMonitoring(intervalMs = 2500) {
        this.stopStatsMonitoring();
        this.statsInterval = setInterval(async () => {
            if (!this.isCurrentAttempt() || !this.peerConnection || this.peerConnection.connectionState !== 'connected') {
                return;
            }
            const rtp = await this.getInboundAudioStats();
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

    disconnect() {
        this.isDisconnecting = true;
        this.isConnecting = false;

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
            this.log(`[WebRTC] [Attempt #${this.connectionAttemptId}] Closing PeerConnection`);
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
        }

        // Stop microphone stream tracks
        if (this.localStream) {
            try {
                this.localStream.getTracks().forEach(track => track.stop());
            } catch (e) {}
            this.localStream = null;
        }

        // Protect shared audio element: only clear if THIS instance attached the active stream!
        if (this.remoteAudio && this.remoteAudio._attachedAttemptId === this.connectionAttemptId) {
            this.log(`[WebRTC] [Attempt #${this.connectionAttemptId}] Clearing remote audio stream (active attempt disconnect)`);
            try {
                this.remoteAudio.pause();
                this.remoteAudio.srcObject = null;
                delete this.remoteAudio._attachedAttemptId;
            } catch (e) {}
        } else {
            this.log(`[WebRTC] [Attempt #${this.connectionAttemptId}] Stale disconnect skipped clearing shared audio element`);
        }

        // Only update global references and UI state if this is the active attempt
        if (this.connectionAttemptId === VoiceClient.activeAttemptId) {
            if (typeof window !== 'undefined' && window.peerConnection === this.peerConnection) {
                window.peerConnection = null;
            }
            this.setState('DISCONNECTED');
        }
    }
}

// Global export for browser script usage
if (typeof window !== 'undefined') {
    window.VoiceClient = VoiceClient;
}

// CommonJS export for Node.js test environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VoiceClient;
}
