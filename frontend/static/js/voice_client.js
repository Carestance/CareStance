/**
 * VoiceClient - WebRTC Conversational AI Client for CareStance.
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
        
        // Ensure remote audio element is properly attached to the DOM so browsers don't restrict playback
        let el = document.getElementById('carestance-remote-audio');
        if (!el) {
            el = document.createElement('audio');
            el.id = 'carestance-remote-audio';
            el.autoplay = true;
            el.playsInline = true;
            el.style.display = 'none';
            document.body.appendChild(el);
        }
        this.remoteAudio = el;
        this.remoteAudio.muted = false;
        this.remoteAudio.volume = 1.0;
        
        // Track connection and interruption state
        this.isConnecting = false;
        this.isDisconnecting = false;
        this.chatHistory = [];
    }

    resolveApiUrl(url) {
        if (!url) return '/api/webrtc/offer';
        return url.replace(/^ws:/, 'http:').replace(/^wss:/, 'https:');
    }

    setState(newState) {
        this.state = newState;
        if (typeof this.onStateChange === 'function') {
            this.onStateChange(newState);
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
        if (this.isConnecting || this.state === 'CONNECTING') return;
        this.isDisconnecting = false;
        this.setState('CONNECTING');
        this.isConnecting = true;

        try {
            if (!window.isSecureContext && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
                throw new Error('Microphone access requires HTTPS.');
            }
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error('This browser does not support microphone access.');
            }

            // Get local microphone stream with echo cancellation and noise suppression
            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                },
                video: false
            });

            // Initialize WebRTC Peer Connection with STUN servers
            const peerConnection = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' }
                ]
            });
            this.peerConnection = peerConnection;

            // Add local tracks to peer connection
            this.localStream.getTracks().forEach(track => {
                peerConnection.addTrack(track, this.localStream);
            });

            // Create Data Channel for transcript and app messages
            this.dataChannel = this.peerConnection.createDataChannel("pipecat");
            
            this.dataChannel.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    this.onMessage(msg);
                } catch (e) {
                    console.log("[VoiceClient] Data channel message (non-JSON):", event.data);
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

            // Send offer to backend
            const response = await fetch(this.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': localStorage.getItem('carestance_client_id') || 'anonymous'
                },
                credentials: 'include',
                body: JSON.stringify({
                    sdp: peerConnection.localDescription.sdp,
                    type: peerConnection.localDescription.type
                })
            });

            if (!response.ok) {
                throw new Error(`Failed to negotiate WebRTC: ${response.statusText}`);
            }

            const answerData = await response.json();
            
            // Set Remote Description (Answer)
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription({
                sdp: answerData.sdp,
                type: answerData.type
            }));
            
            // Save session_id for future tracking
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
            this.isConnecting = false;
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
        
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }

        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
            this.localStream = null;
        }

        if (this.remoteAudio) {
            this.remoteAudio.srcObject = null;
            this.remoteAudio.pause();
        }

        this.setState(nextState);
    }
}

// Global export for browser script usage
window.VoiceClient = VoiceClient;
