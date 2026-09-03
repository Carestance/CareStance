/**
 * VoiceClient - WebRTC Conversational AI Client for CareStance.
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
        this.remoteAudio = document.createElement('audio');
        this.remoteAudio.autoplay = true;
        
        // Track connection and interruption state
        this.isConnecting = false;
        this.isDisconnecting = false;
        this.chatHistory = [];
    }

    setState(newState) {
        this.state = newState;
        if (typeof this.onStateChange === 'function') {
            this.onStateChange(newState);
        }
    }

    async connect() {
        if (this.isConnecting || this.state === 'CONNECTING') return;
        this.isDisconnecting = false;
        this.setState('CONNECTING');
        this.isConnecting = true;

        try {
            // Get local microphone stream
            this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });

            // Initialize WebRTC Peer Connection
            this.peerConnection = new RTCPeerConnection();

            // Add local tracks to peer connection
            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });

            // Create Data Channel for transcript and app messages
            this.dataChannel = this.peerConnection.createDataChannel("pipecat");
            
            this.dataChannel.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    this.onMessage(msg);
                } catch (e) {
                    console.log("Data channel message (non-JSON):", event.data);
                }
            };

            // Handle incoming remote audio stream
            this.peerConnection.ontrack = (event) => {
                if (event.streams && event.streams[0]) {
                    this.remoteAudio.srcObject = event.streams[0];
                }
            };

            this.peerConnection.onconnectionstatechange = () => {
                if (this.peerConnection.connectionState === 'connected') {
                    this.setState('LISTENING');
                } else if (this.peerConnection.connectionState === 'disconnected' || 
                           this.peerConnection.connectionState === 'failed') {
                    this.disconnect();
                }
            };

            // Create WebRTC Offer
            const offer = await this.peerConnection.createOffer();
            await this.peerConnection.setLocalDescription(offer);

            // Send offer to backend
            const response = await fetch(this.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': localStorage.getItem('carestance_client_id') || 'anonymous'
                },
                body: JSON.stringify({
                    sdp: this.peerConnection.localDescription.sdp,
                    type: this.peerConnection.localDescription.type
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
            this.setState('ERROR');
            this.disconnect();
        } finally {
            this.isConnecting = false;
        }
    }

    async handleUserSpeech(text) {
        // In WebRTC mode, speech is automatically streamed to the backend.
        // This method is kept for backwards compatibility with the UI transcript handler
        if (!text) return;
        this.onMessage(text, 'user');
        this.chatHistory.push({ role: 'user', content: text });
    }

    speak(text) {
        // In WebRTC mode, audio plays automatically via remoteAudio.
        // We just update the state/UI.
        this.onMessage(text, 'assistant');
        this.setState('SPEAKING');
    }

    disconnect() {
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
        }

        this.setState('DISCONNECTED');
    }
}

// Global export for browser script usage
window.VoiceClient = VoiceClient;
