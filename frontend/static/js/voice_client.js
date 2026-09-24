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

    constructor(wsUrl, onStateChange, onMessage, options = {}) {
        // wsUrl is repurposed as the API endpoint for WebRTC offer exchange if provided,
        // otherwise it defaults to the /api/webrtc/offer endpoint.
        this.apiUrl = wsUrl ? wsUrl.replace("ws://", "http://").replace("wss://", "https://") : '/api/webrtc/offer';
        this.configUrl = (options && options.configUrl) || (this.apiUrl && this.apiUrl.endsWith('/offer') ? this.apiUrl.replace(/\/offer$/, '/config') : '/api/webrtc/config');
        this.iceServers = (options && options.iceServers) || null;
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
        return (
            this.isCurrentAttempt(attemptId) &&
            pc &&
            this.peerConnection === pc &&
            pc.signalingState !== 'closed'
        );
    }

    setState(newState, attemptId = this.connectionAttemptId) {
        const isTerminalState = (newState === 'DISCONNECTED' || newState === 'ERROR');
        if (!isTerminalState) {
            if (!this.isCurrentAttempt(attemptId)) {
                this.log(`[WebRTC] Ignoring setState('${newState}') for stale attempt ${attemptId}`);
                return;
            }
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
    setupAutoplayUnlock(attemptId = this.connectionAttemptId) {
        if (typeof document === 'undefined') return;

        this.log("[WebRTC] Registering user-interaction fallback for audio unlock");
        const unlock = () => {
            if (this.isCurrentAttempt(attemptId) && this.remoteAudio && this.remoteAudio.srcObject) {
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
    waitForIceGatheringComplete(pc, timeoutMs = 3000) {
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

            // 2. Resolve ICE Servers configuration (STUN + TURN)
            let iceServers = this.iceServers;
            if (!iceServers) {
                iceServers = [
                    { urls: ['stun:stun.l.google.com:19302'] },
                    { urls: ['stun:stun1.l.google.com:19302'] },
                    { urls: ['stun:stun2.l.google.com:19302'] }
                ];
                try {
                    const configResp = await fetch(this.configUrl, {
                        method: 'GET',
                        headers: { 'Accept': 'application/json' },
                        signal: this.abortController ? this.abortController.signal : undefined
                    });
                    if (configResp.ok) {
                        const configData = await configResp.json();
                        if (configData && configData.error) {
                            console.error(`[WebRTC] [Attempt #${attemptId}] SERVER REPORTED ICE CONFIG ERROR: ${configData.error}`);
                        }
                        if (configData && Array.isArray(configData.iceServers) && configData.iceServers.length > 0) {
                            iceServers = configData.iceServers;
                            this.log(`[WebRTC] [Attempt #${attemptId}] Loaded ICE configuration from server (${iceServers.length} server(s) configured)`);
                            
                            // Safe structural diagnostic logging without exposing secrets
                            let hasTurn = false;
                            iceServers.forEach((s, idx) => {
                                const urls = Array.isArray(s.urls) ? s.urls : [s.urls];
                                urls.forEach(u => {
                                    if (typeof u === 'string') {
                                        const isTurn = u.startsWith('turn:') || u.startsWith('turns:');
                                        if (isTurn) hasTurn = true;
                                        let scheme = 'unknown';
                                        let host = 'unknown';
                                        let transport = 'default';
                                        if (u.includes(':')) {
                                            const parts = u.split(':');
                                            scheme = parts[0];
                                            const rest = parts.slice(1).join(':');
                                            if (rest.includes('?')) {
                                                const [hostPart, query] = rest.split('?');
                                                host = hostPart.replace(/^\/\//, '');
                                                const qParams = new URLSearchParams(query);
                                                transport = qParams.get('transport') || (scheme === 'turns' ? 'tcp' : 'udp');
                                            } else {
                                                host = rest.replace(/^\/\//, '');
                                                transport = scheme === 'turns' ? 'tcp' : 'udp';
                                            }
                                        }
                                        this.log(`[WebRTC] ICE Server #${idx + 1}: scheme=${scheme} host=${host} transport=${transport} hasUser=${Boolean(s.username)} hasCred=${Boolean(s.credential)}`);
                                    }
                                });
                            });
                            if (!hasTurn) {
                                console.warn(`[WebRTC] [Attempt #${attemptId}] CRITICAL WARNING: No TURN server is present in the ICE configuration! Only STUN/host candidates will be used. Relay allocation will NOT occur.`);
                            } else {
                                this.log(`[WebRTC] [Attempt #${attemptId}] TURN relay server configured with credentials`);
                            }
                        }
                    }
                } catch (configErr) {
                    if (configErr.name === 'AbortError') throw configErr;
                    this.log(`[WebRTC] [Attempt #${attemptId}] Failed to load ICE config from server, falling back to default STUN:`, configErr.message);
                }
            }

            // Check if connection was aborted while fetching ICE config
            if (!this.isCurrentAttempt(attemptId)) {
                this.log(`[WebRTC] [Attempt #${attemptId}] Stale PeerConnection attempt after ICE config fetch aborted; stopping local tracks`);
                if (this.localStream) {
                    this.localStream.getTracks().forEach(t => t.stop());
                    this.localStream = null;
                }
                return;
            }

            // 3. Create RTCPeerConnection and capture its reference
            this.log(`[WebRTC] [Attempt #${attemptId}] Creating PeerConnection with ${iceServers.length} ICE server(s)`);
            const pc = new RTCPeerConnection({
                iceServers: iceServers
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
                                this.setupAutoplayUnlock(attemptId);
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
            pc.onconnectionstatechange = async () => {
                if (!this.isValidPeerConnection(pc, attemptId)) {
                    this.log(`[WebRTC] [Attempt #${attemptId}] Stale connectionstatechange ignored (state=${pc ? pc.connectionState : 'null'})`);
                    return;
                }
                const cState = pc.connectionState;
                this.log(`[WebRTC] [Attempt #${attemptId}] connectionState=${cState}`);
                await this.collectIceDiagnostics(pc, attemptId, `Connection State: ${cState}`);
                
                if (cState === 'connected') {
                    this.setState('LISTENING', attemptId);
                    this.startStatsMonitoring(2500, attemptId);
                } else if (cState === 'disconnected' || cState === 'failed') {
                    console.warn(`[WebRTC] [Attempt #${attemptId}] Connection state changed to ${cState}`);
                    await this.collectIceDiagnostics(pc, attemptId, "FINAL ICE DIAGNOSTICS");
                    if (cState === 'failed' && typeof this.onMessage === 'function') {
                        this.onMessage({
                            type: 'VOICE_ERROR',
                            code: 'ICE_CONNECTION_FAILED',
                            message: 'WebRTC connection failed: ICE connectivity could not be established.'
                        });
                    }
                    this.disconnect(cState === 'failed' ? 'ERROR' : 'DISCONNECTED');
                }
            };

            pc.oniceconnectionstatechange = async () => {
                if (!this.isValidPeerConnection(pc, attemptId)) return;
                const iceState = pc.iceConnectionState;
                this.log(`[WebRTC] [Attempt #${attemptId}] iceConnectionState=${iceState}`);
                await this.collectIceDiagnostics(pc, attemptId, `ICE State: ${iceState}`);
                if (iceState === 'failed') {
                    console.error(`[WebRTC] [Attempt #${attemptId}] ICE failure detected`);
                    await this.collectIceDiagnostics(pc, attemptId, "FINAL ICE DIAGNOSTICS");
                    if (typeof this.onMessage === 'function') {
                        this.onMessage({
                            type: 'VOICE_ERROR',
                            code: 'ICE_CONNECTION_FAILED',
                            message: 'WebRTC connection failed: ICE connectivity could not be established.'
                        });
                    }
                    this.disconnect('ERROR');
                }
            };

            pc.onsignalingstatechange = () => {
                if (!this.isValidPeerConnection(pc, attemptId)) return;
                const sigState = pc.signalingState;
                this.log(`[WebRTC] [Attempt #${attemptId}] signalingState=${sigState}`);
            };

            // Monitor candidate gathering and candidate errors
            let relayCount = 0;
            let totalCandidates = 0;
            pc.onicecandidate = (event) => {
                if (!this.isValidPeerConnection(pc, attemptId)) return;
                if (event.candidate) {
                    totalCandidates++;
                    const c = event.candidate;
                    const isRelay = c.type === 'relay' || (c.candidate && c.candidate.includes('typ relay'));
                    if (isRelay) {
                        relayCount++;
                        this.log(`[WebRTC] [Attempt #${attemptId}] >>> RELAY CANDIDATE GATHERED: protocol=${c.protocol} address=${c.address} port=${c.port} url=${c.url || 'none'} <<<`);
                    } else {
                        this.log(`[WebRTC] [Attempt #${attemptId}] Local candidate: type=${c.type} protocol=${c.protocol} address=${c.address} port=${c.port}`);
                    }
                } else {
                    this.log(`[WebRTC] [Attempt #${attemptId}] ICE gathering completed: total=${totalCandidates}, relay=${relayCount}`);
                    if (relayCount === 0) {
                        console.warn(`[WebRTC] [Attempt #${attemptId}] WARNING: 0 relay candidates gathered. If STUN binding fails, check TURN server reachability and credentials.`);
                    }
                }
            };

            pc.onicecandidateerror = (event) => {
                if (!this.isValidPeerConnection(pc, attemptId)) return;
                console.warn(`[WebRTC] [Attempt #${attemptId}] [ICE Candidate Error] url=${event.url || 'unknown'} errorCode=${event.errorCode} errorText="${event.errorText}" address=${event.address || 'unknown'} port=${event.port || 'unknown'}`);
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
            await this.waitForIceGatheringComplete(pc, 3000);
            if (!this.isValidPeerConnection(pc, attemptId)) {
                this.log(`[WebRTC] [Attempt #${attemptId}] Aborted after ICE gathering wait; PeerConnection reference changed or closed`);
                return;
            }

            // 10. Inspect candidate presence and send offer
            const hasCandidates = pc.localDescription && pc.localDescription.sdp.includes("a=candidate:");
            this.log(`[WebRTC] [Attempt #${attemptId}] SDP contains candidates: ${hasCandidates}`);
            if (pc.localDescription && pc.localDescription.sdp) {
                const sanitizedOffer = pc.localDescription.sdp.replace(/a=ice-pwd:\S+/g, 'a=ice-pwd:[REDACTED]');
                this.log(`[WebRTC] [Attempt #${attemptId}] Sanitized SDP Offer:\n` + sanitizedOffer);
            }
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
            if (answerData && answerData.sdp) {
                const sanitizedAnswer = answerData.sdp.replace(/a=ice-pwd:\S+/g, 'a=ice-pwd:[REDACTED]');
                this.log(`[WebRTC] [Attempt #${attemptId}] Sanitized SDP Answer:\n` + sanitizedAnswer);
            }

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
            if (typeof this.onMessage === 'function') {
                this.onMessage({
                    type: 'VOICE_ERROR',
                    code: error.name || 'VOICE_CONNECTION_FAILED',
                    message: error.message || 'Unable to establish WebRTC connection.'
                });
            }
            if (this.isCurrentAttempt(attemptId)) {
                this.disconnect('ERROR');
            }
        } finally {
            if (this.connectionAttemptId === attemptId) {
                this.isConnecting = false;
            }
        }
    }
    /**
     * Collects and logs structured ICE, candidate pair, and RTP diagnostics.
     */
    async collectIceDiagnostics(pc, attemptId, label = "ICE DIAGNOSTICS") {
        if (!pc || typeof pc.getStats !== 'function') return null;
        try {
            const stats = await pc.getStats();
            const candidatePairs = [];
            const localCandidates = {};
            const remoteCandidates = {};
            let inboundRtp = null;
            let outboundRtp = null;
            let selectedPair = null;

            if (stats && typeof stats.forEach === 'function') {
                stats.forEach(report => {
                    if (report.type === 'candidate-pair') {
                        const pair = {
                            id: report.id,
                            state: report.state,
                            nominated: !!report.nominated,
                            selected: !!report.selected,
                            bytesSent: report.bytesSent || 0,
                            bytesReceived: report.bytesReceived || 0,
                            packetsSent: report.packetsSent || 0,
                            packetsReceived: report.packetsReceived || 0,
                            requestsSent: report.requestsSent || 0,
                            responsesReceived: report.responsesReceived || 0,
                            requestsReceived: report.requestsReceived || 0,
                            responsesSent: report.responsesSent || 0,
                            currentRoundTripTime: report.currentRoundTripTime,
                            localCandidateId: report.localCandidateId,
                            remoteCandidateId: report.remoteCandidateId
                        };
                        candidatePairs.push(pair);
                        if (report.selected || report.nominated) {
                            selectedPair = pair;
                        }
                    } else if (report.type === 'local-candidate') {
                        const cand = {
                            id: report.id,
                            candidateType: report.candidateType,
                            protocol: report.protocol,
                            address: report.address || report.ip,
                            port: report.port,
                            relatedAddress: report.relatedAddress,
                            relatedPort: report.relatedPort
                        };
                        localCandidates[report.id] = cand;
                        if (report.candidateType === 'relay') {
                            this.log(`[WebRTC] [Attempt #${attemptId}] TURN candidate detected (local-candidate): candidateType=relay protocol=${report.protocol} address=${cand.address}:${cand.port}`);
                        }
                    } else if (report.type === 'remote-candidate') {
                        const cand = {
                            id: report.id,
                            candidateType: report.candidateType,
                            protocol: report.protocol,
                            address: report.address || report.ip,
                            port: report.port,
                            relatedAddress: report.relatedAddress,
                            relatedPort: report.relatedPort
                        };
                        remoteCandidates[report.id] = cand;
                        if (report.candidateType === 'relay') {
                            this.log(`[WebRTC] [Attempt #${attemptId}] TURN candidate detected (remote-candidate): candidateType=relay protocol=${report.protocol} address=${cand.address}:${cand.port}`);
                        }
                    } else if (report.type === 'inbound-rtp' && (report.kind === 'audio' || report.mediaType === 'audio')) {
                        inboundRtp = {
                            packetsReceived: report.packetsReceived || 0,
                            bytesReceived: report.bytesReceived || 0,
                            packetsLost: report.packetsLost || 0,
                            jitter: report.jitter !== undefined ? report.jitter : null,
                            audioLevel: report.audioLevel !== undefined ? report.audioLevel : null,
                            timestamp: report.timestamp
                        };
                    } else if (report.type === 'outbound-rtp' && (report.kind === 'audio' || report.mediaType === 'audio')) {
                        outboundRtp = {
                            packetsSent: report.packetsSent || 0,
                            bytesSent: report.bytesSent || 0,
                            timestamp: report.timestamp
                        };
                    }
                });
            }

            if (selectedPair) {
                const local = localCandidates[selectedPair.localCandidateId];
                const remote = remoteCandidates[selectedPair.remoteCandidateId];
                const localType = (local && local.candidateType) || 'unknown';
                const remoteType = (remote && remote.candidateType) || 'unknown';
                const protocol = (local && local.protocol) || selectedPair.protocol || 'udp';
                selectedPair.localType = localType;
                selectedPair.remoteType = remoteType;
                selectedPair.protocol = protocol;
                this.log(`[WebRTC] [Attempt #${attemptId}] Selected ICE Pair: localType=${localType} remoteType=${remoteType} protocol=${protocol} state=${selectedPair.state} nominated=${selectedPair.nominated} selected=${selectedPair.selected}`);
            }

            const diag = {
                attemptId,
                label,
                signalingState: pc.signalingState,
                iceGatheringState: pc.iceGatheringState,
                iceConnectionState: pc.iceConnectionState,
                connectionState: pc.connectionState,
                selectedPair,
                candidatePairs,
                localCandidates: Object.values(localCandidates),
                remoteCandidates: Object.values(remoteCandidates),
                inboundRtp,
                outboundRtp
            };

            this.log(`[WebRTC] [Attempt #${attemptId}] ${label}:`, JSON.stringify(diag, null, 2));
            return diag;
        } catch (e) {
            this.log(`[WebRTC] [Attempt #${attemptId}] Failed to collect ${label}:`, e);
            return null;
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

    startStatsMonitoring(intervalMs = 2500, attemptId = this.connectionAttemptId) {
        this.stopStatsMonitoring();
        this.statsInterval = setInterval(async () => {
            if (!this.isCurrentAttempt(attemptId) || !this.peerConnection || this.peerConnection.connectionState !== 'connected') {
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
        this.setState('SPEAKING', this.connectionAttemptId);
    }

    disconnect(nextState = 'DISCONNECTED') {
        const disconnectedAttemptId = this.connectionAttemptId;
        const wasActive = (disconnectedAttemptId > 0 && disconnectedAttemptId === VoiceClient.activeAttemptId);

        this.isDisconnecting = true;
        this.isConnecting = false;

        // Invalidate activeAttemptId immediately so no in-flight async operations can continue
        if (wasActive) {
            VoiceClient.activeAttemptId = 0;
            if (VoiceClient.activeClient === this) {
                VoiceClient.activeClient = null;
            }
        }

        this.stopStatsMonitoring();

        // Abort in-flight HTTP offer request
        if (this.abortController) {
            try {
                this.abortController.abort();
            } catch (e) {}
            this.abortController = null;
        }

        const pcToClose = this.peerConnection;
        // Close peer connection cleanly
        if (pcToClose) {
            this.log(`[WebRTC] [Attempt #${disconnectedAttemptId}] Closing PeerConnection`);
            try {
                pcToClose.ontrack = null;
                pcToClose.oniceconnectionstatechange = null;
                pcToClose.onconnectionstatechange = null;
                pcToClose.onsignalingstatechange = null;
                pcToClose.close();
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
        if (this.remoteAudio && this.remoteAudio._attachedAttemptId === disconnectedAttemptId) {
            this.log(`[WebRTC] [Attempt #${disconnectedAttemptId}] Clearing remote audio stream (active attempt disconnect)`);
            try {
                this.remoteAudio.pause();
                this.remoteAudio.srcObject = null;
                delete this.remoteAudio._attachedAttemptId;
            } catch (e) {}
        } else {
            this.log(`[WebRTC] [Attempt #${disconnectedAttemptId}] Stale disconnect skipped clearing shared audio element`);
        }

        // Only update global references and UI state if this was the active attempt
        if (wasActive) {
            if (typeof window !== 'undefined' && window.peerConnection === pcToClose) {
                window.peerConnection = null;
            }
            this.setState(nextState, disconnectedAttemptId);
        }
    }
}

// Global export for browser script usage
if (typeof window !== 'undefined') {
    window.VoiceClient = VoiceClient;
}

// Runtime verification diagnostic
if (typeof console !== 'undefined' && typeof VoiceClient !== 'undefined') {
    console.log('[VoiceClient Runtime]', {
        source: 'voice_client.js',
        hasIsCurrentAttempt: typeof VoiceClient?.prototype?.isCurrentAttempt === 'function',
        hasIsValidPeerConnection: typeof VoiceClient?.prototype?.isValidPeerConnection === 'function',
        prototypeMethods: VoiceClient ? Object.getOwnPropertyNames(VoiceClient.prototype) : []
    });
}

// CommonJS export for Node.js test environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VoiceClient;
}
