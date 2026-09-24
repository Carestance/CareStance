/**
 * VoiceClient - WebRTC Conversational AI Client for CareStance.
 * Robust, singleton-managed WebRTC lifecycle with structured logging,
 * full ICE candidate gathering, autoplay handling, and inbound RTP metrics.
 */
class VoiceClient {
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

    /**
     * Fallback autoplay unlock handler if browser policy prevents initial play.
     */
    setupAutoplayUnlock() {
        this.log("[WebRTC] Registering user-interaction fallback for audio unlock");
        const unlock = () => {
            if (this.remoteAudio && this.remoteAudio.srcObject) {
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
            // Cancel any previous in-flight fetch request
            if (this.abortController) {
                this.abortController.abort();
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

            // Check if connection was aborted while waiting for mic permission
            if (this.currentAttemptId !== attemptId || this.isDisconnecting) {
                this.log("[WebRTC] stale PeerConnection attempt after getUserMedia aborted");
                if (this.localStream) {
                    this.localStream.getTracks().forEach(t => t.stop());
                    this.localStream = null;
                }
                return;
            }

            // 2. Create RTCPeerConnection
            this.log("[WebRTC] Creating PeerConnection");
            const pc = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' },
                    { urls: 'stun:stun2.l.google.com:19302' }
                ]
            });
            this.peerConnection = pc;
            window.peerConnection = pc; // Expose globally for diagnostics and kiosk telemetry

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
                try {
                    const msg = JSON.parse(event.data);
                    this.onMessage(msg);
                } catch (e) {
                    this.log("[VoiceClient] Data channel message (non-JSON):", event.data);
                }
            };

            // 5. Handle remote audio track & play directly through audio element
            pc.ontrack = (event) => {
                if (this.currentAttemptId !== attemptId) return;

                if (event.track.kind !== "audio") {
                    this.log("[WebRTC] Remote track received (ignored non-audio):", event.track.kind);
                    return;
                }

                this.log("[WebRTC] Remote track received", {
                    kind: event.track.kind,
                    id: event.track.id,
                    readyState: event.track.readyState,
                    muted: event.track.muted,
                    streamId: (event.streams && event.streams[0]) ? event.streams[0].id : "new"
                });

                const stream = (event.streams && event.streams[0]) 
                    ? event.streams[0] 
                    : new MediaStream([event.track]);

                this.remoteAudio.srcObject = stream;
                this.remoteAudio.muted = false;
                this.remoteAudio.volume = 1.0;
                this.remoteAudio.autoplay = true;
                this.remoteAudio.playsInline = true;

                this.log("[WebRTC] Remote audio stream attached");
                this.logAudioState();

                const playPromise = this.remoteAudio.play();
                if (playPromise !== undefined) {
                    playPromise.then(() => {
                        this.log("[WebRTC] Audio playback started");
                        this.logAudioState();
                    }).catch((error) => {
                        console.error("[WebRTC] Audio playback failed:", error);
                        this.logAudioState();
                        if (error.name === "NotAllowedError") {
                            this.setupAutoplayUnlock();
                        }
                    });
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

            // 6. Monitor connection, ICE, and signaling states
            pc.onconnectionstatechange = () => {
                if (this.currentAttemptId !== attemptId) return;
                const cState = pc ? pc.connectionState : 'closed';
                this.log(`[WebRTC] Connection state: ${cState}`);
                
                if (cState === 'connected') {
                    this.setState('LISTENING');
                    this.startStatsMonitoring();
                } else if (cState === 'disconnected' || cState === 'failed') {
                    console.warn(`[WebRTC] Connection state changed to ${cState}`);
                    this.disconnect();
                }
            };

            pc.oniceconnectionstatechange = () => {
                if (this.currentAttemptId !== attemptId) return;
                const iceState = pc ? pc.iceConnectionState : 'closed';
                this.log(`[WebRTC] ICE state: ${iceState}`);
                if (iceState === 'failed') {
                    console.error("[WebRTC] ICE failure detected");
                    this.disconnect();
                }
            };

            pc.onsignalingstatechange = () => {
                if (this.currentAttemptId !== attemptId) return;
                const sigState = pc ? pc.signalingState : 'closed';
                this.log(`[WebRTC] Signaling state: ${sigState}`);
            };

            // 7. Create WebRTC Offer
            this.log("[WebRTC] Creating offer");
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            // 8. Wait for ICE gathering to complete (Vanilla ICE)
            // Backend endpoint /api/webrtc/offer is a single POST request without trickle ICE.
            // Gather all candidate info into localDescription.sdp before sending.
            if (pc.iceGatheringState !== 'complete') {
                this.log("[WebRTC] Waiting for ICE gathering to complete");
                await new Promise((resolve) => {
                    let timeoutId = null;
                    const onGatherChange = () => {
                        if (pc.iceGatheringState === 'complete') {
                            if (timeoutId) clearTimeout(timeoutId);
                            pc.removeEventListener('icegatheringstatechange', onGatherChange);
                            resolve();
                        }
                    };
                    pc.addEventListener('icegatheringstatechange', onGatherChange);
                    // Safe maximum timeout of 1500ms so we never block connection flow
                    timeoutId = setTimeout(() => {
                        pc.removeEventListener('icegatheringstatechange', onGatherChange);
                        this.log("[WebRTC] ICE gathering window elapsed, proceeding with gathered candidates");
                        resolve();
                    }, 1500);
                });
            }

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
                    sdp: pc.localDescription.sdp,
                    type: pc.localDescription.type
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
            // Ignore intentional abort errors from disconnect()
            if (error.name === 'AbortError') {
                this.log("[WebRTC] Network request cancelled via AbortController");
                return;
            }

            console.error("[WebRTC] WebRTC Connection failed:", error);
            if (this.currentAttemptId === attemptId) {
                this.setState('ERROR');
                this.disconnect();
            }
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

    disconnect() {
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

        this.setState('DISCONNECTED');
    }
}

// Global export for browser script usage
window.VoiceClient = VoiceClient;
