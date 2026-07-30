/**
 * VoiceClient - Web Speech Recognition & Speech Synthesis Voice Client for CareStance Phase 3 & Milestone Chats.
 */
class VoiceClient {
    constructor(wsUrl, onStateChange, onMessage) {
        this.wsUrl = wsUrl;
        this.onStateChange = onStateChange || function() {};
        this.onMessage = onMessage || function() {};
        this.state = 'IDLE';
        this.socket = null;
        this.recognition = null;
        this.isConnecting = false;
        this.isDisconnecting = false;
        this.chatHistory = [];
        
        this.initSpeechRecognition();
    }

    setState(newState) {
        this.state = newState;
        if (typeof this.onStateChange === 'function') {
            this.onStateChange(newState);
        }
    }

    initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn("SpeechRecognition API is not supported in this browser.");
            return;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';

        let finalTranscript = '';

        this.recognition.onstart = () => {
            finalTranscript = '';
            if (this.state !== 'SPEAKING' && this.state !== 'THINKING') {
                this.setState('LISTENING');
            }
        };

        this.recognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interim += event.results[i][0].transcript;
                }
            }

            const displayElem = document.getElementById('transcript-display');
            if (displayElem && (interim || finalTranscript)) {
                displayElem.textContent = interim || finalTranscript;
            }

            if (finalTranscript.trim()) {
                const text = finalTranscript.trim();
                finalTranscript = '';
                this.handleUserSpeech(text);
            }
        };

        this.recognition.onerror = (event) => {
            console.warn("SpeechRecognition error:", event.error);
            if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                this.setState('ERROR');
            } else if (this.state === 'LISTENING') {
                // Ignore silent timeouts or non-fatal errors
            }
        };

        this.recognition.onend = () => {
            if (!this.isDisconnecting && ['LISTENING', 'CONNECTING'].includes(this.state)) {
                // Restart listening if active and not speaking or thinking
                try {
                    this.recognition.start();
                } catch (e) {}
            }
        };
    }

    connect() {
        this.isDisconnecting = false;
        this.setState('CONNECTING');

        // Attempt WebSocket connection if endpoint available
        if (this.wsUrl) {
            try {
                this.socket = new WebSocket(this.wsUrl);
                this.socket.onopen = () => {
                    this.setState('LISTENING');
                    this.startListening();
                };

                this.socket.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'transcript' || data.type === 'response') {
                            this.onMessage(data.text, data.role || 'assistant');
                            if (data.role === 'assistant') {
                                this.speak(data.text);
                            }
                        }
                    } catch (e) {
                        if (typeof event.data === 'string') {
                            this.onMessage(event.data, 'assistant');
                            this.speak(event.data);
                        }
                    }
                };

                this.socket.onerror = (err) => {
                    console.log("WebSocket connection failed, falling back to Web Speech API + HTTP API");
                    this.socket = null;
                    this.wsUrl = null; // Disable future WebSocket attempts to stop 403 spam
                    this.setState('LISTENING');
                    this.startListening();
                };

                this.socket.onclose = (event) => {
                    if (!this.isDisconnecting && this.state !== 'DISCONNECTED') {
                        // If closed before ever opening (e.g. 403), disable WebSocket permanently
                        if (event.code !== 1000 && event.code !== 1001) {
                            this.wsUrl = null;
                        }
                        this.socket = null;
                        this.setState('LISTENING');
                        this.startListening();
                    }
                };
            } catch (e) {
                this.socket = null;
                this.setState('LISTENING');
                this.startListening();
            }
        } else {
            this.setState('LISTENING');
            this.startListening();
        }
    }

    startListening() {
        if (this.recognition) {
            try {
                this.recognition.start();
            } catch (e) {
                // Might already be running
            }
        }
    }

    async handleUserSpeech(text) {
        if (!text) return;

        // Display user transcript
        this.onMessage(text, 'user');
        this.chatHistory.push({ role: 'user', content: text });

        // Stop recognition while thinking / speaking
        if (this.recognition) {
            try { this.recognition.stop(); } catch(e) {}
        }

        // If WebSocket is active, send through socket
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.setState('THINKING');
            this.socket.send(JSON.stringify({ type: 'text', text: text }));
            return;
        }

        // Fallback: Send to HTTP backend endpoint /assessment/phase3/chat_v2
        this.setState('THINKING');
        try {
            const resp = await fetch('/assessment/phase3/chat_v2', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    answers: this.chatHistory
                })
            });

            if (resp.ok) {
                const data = await resp.json();
                const aiText = data.response || "Thank you for sharing that. Tell me more about your thoughts.";
                this.chatHistory.push({ role: 'assistant', content: aiText });
                this.onMessage(aiText, 'assistant');
                this.speak(aiText);
            } else {
                const fallbackText = "I'm reflecting on what you said. Could you expand on that?";
                this.onMessage(fallbackText, 'assistant');
                this.speak(fallbackText);
            }
        } catch (err) {
            console.error("Error calling chat endpoint:", err);
            const fallbackText = "That's very insightful. What else comes to mind when you think about your career goals?";
            this.onMessage(fallbackText, 'assistant');
            this.speak(fallbackText);
        }
    }

    speak(text) {
        if (!('speechSynthesis' in window)) {
            this.setState('LISTENING');
            this.startListening();
            return;
        }

        window.speechSynthesis.cancel(); // Stop any active speech

        // Strip Markdown tags for natural speech synthesis
        const cleanText = text.replace(/[*_#`~[\]()]/g, '').trim();
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        // Try selecting a natural English voice if available
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha')));
        if (preferredVoice) {
            utterance.voice = preferredVoice;
        }

        utterance.onstart = () => {
            this.setState('SPEAKING');
        };

        utterance.onend = () => {
            if (!this.isDisconnecting) {
                this.setState('LISTENING');
                this.startListening();
            }
        };

        utterance.onerror = (err) => {
            console.warn("SpeechSynthesis error:", err);
            if (!this.isDisconnecting) {
                this.setState('LISTENING');
                this.startListening();
            }
        };

        window.speechSynthesis.speak(utterance);
    }

    disconnect() {
        this.isDisconnecting = true;
        
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }

        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (e) {}
        }

        if (this.socket) {
            try {
                this.socket.close();
            } catch (e) {}
            this.socket = null;
        }

        this.setState('DISCONNECTED');
    }
}

// Global export for browser script usage
window.VoiceClient = VoiceClient;
