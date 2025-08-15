/**
 * SoulLink Tracker Dashboard - WebSocket Client
 * Handles real-time communication with the SoulLink Tracker API
 */

class WebSocketClient {
    constructor(url, options = {}) {
        this.url = url;
        this.options = {
            reconnectInterval: 3000,
            maxReconnectAttempts: 10,
            heartbeatInterval: 30000,
            debug: false,
            ...options
        };
        
        this.ws = null;
        this.reconnectAttempts = 0;
        this.heartbeatTimer = null;
        this.isConnected = false;
        this.shouldReconnect = true;
        this.eventListeners = new Map();
        this.messageQueue = [];
        
        // Bind methods to preserve context
        this.onOpen = this.onOpen.bind(this);
        this.onMessage = this.onMessage.bind(this);
        this.onClose = this.onClose.bind(this);
        this.onError = this.onError.bind(this);
        
        this.log('WebSocket client initialized');
    }
    
    /**
     * Connect to the WebSocket server
     */
    connect() {
        if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
            this.log('WebSocket is already connecting or connected');
            return;
        }
        
        this.log(`Connecting to ${this.url}`);
        
        try {
            this.ws = new WebSocket(this.url);
            this.ws.onopen = this.onOpen;
            this.ws.onmessage = this.onMessage;
            this.ws.onclose = this.onClose;
            this.ws.onerror = this.onError;
        } catch (error) {
            this.log('Failed to create WebSocket connection:', error);
            this.scheduleReconnect();
        }
    }
    
    /**
     * Disconnect from the WebSocket server
     */
    disconnect() {
        this.shouldReconnect = false;
        this.clearHeartbeat();
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        this.isConnected = false;
        this.emit('disconnected');
        this.log('WebSocket disconnected');
    }
    
    /**
     * Send a message to the server
     * @param {Object} message - Message object to send
     */
    send(message) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            try {
                this.ws.send(JSON.stringify(message));
                this.log('Message sent:', message);
            } catch (error) {
                this.log('Failed to send message:', error);
                this.messageQueue.push(message);
            }
        } else {
            this.log('WebSocket not connected, queuing message:', message);
            this.messageQueue.push(message);
        }
    }
    
    /**
     * Add event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
    }
    
    /**
     * Remove event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function to remove
     */
    off(event, callback) {
        if (this.eventListeners.has(event)) {
            const listeners = this.eventListeners.get(event);
            const index = listeners.indexOf(callback);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        }
    }
    
    /**
     * Emit event to listeners
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    emit(event, data) {
        if (this.eventListeners.has(event)) {
            this.eventListeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    this.log('Error in event listener:', error);
                }
            });
        }
    }
    
    /**
     * WebSocket open event handler
     */
    onOpen() {
        this.log('WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        
        // Send queued messages
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            this.send(message);
        }
        
        this.startHeartbeat();
        this.emit('connected');
    }
    
    /**
     * WebSocket message event handler
     * @param {MessageEvent} event - Message event
     */
    onMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.log('Message received:', data);
            
            // Handle different message types
            if (data.type) {
                this.emit(data.type, data);
                this.emit('message', data);
            } else {
                this.emit('message', data);
            }
        } catch (error) {
            this.log('Failed to parse message:', error);
            this.emit('error', { type: 'parse_error', error });
        }
    }
    
    /**
     * WebSocket close event handler
     * @param {CloseEvent} event - Close event
     */
    onClose(event) {
        this.log(`WebSocket closed: ${event.code} - ${event.reason}`);
        this.isConnected = false;
        this.clearHeartbeat();
        
        this.emit('disconnected', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean
        });
        
        // Handle authentication-related close codes
        if (event.code === 4001) {
            console.error('WebSocket authentication failed. Check your login credentials.');
            this.emit('auth_error', { reason: event.reason });
            // Don't try to reconnect on auth failures
            return;
        } else if (event.code === 4003) {
            console.error('Player not authorized for this run.');
            this.emit('auth_error', { reason: event.reason });
            return;
        } else if (event.code === 4004) {
            console.error('Run not found.');
            this.emit('auth_error', { reason: event.reason });
            return;
        }
        
        if (this.shouldReconnect && !event.wasClean) {
            this.scheduleReconnect();
        }
    }
    
    /**
     * WebSocket error event handler
     * @param {Event} event - Error event
     */
    onError(event) {
        this.log('WebSocket error:', event);
        this.emit('error', { type: 'connection_error', event });
    }
    
    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        if (!this.shouldReconnect || this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            this.log('Max reconnection attempts reached');
            this.emit('reconnect_failed');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.options.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1);
        
        this.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
        
        setTimeout(() => {
            if (this.shouldReconnect) {
                this.emit('reconnecting', { attempt: this.reconnectAttempts });
                this.connect();
            }
        }, delay);
    }
    
    /**
     * Start heartbeat to keep connection alive
     */
    startHeartbeat() {
        this.clearHeartbeat();
        
        this.heartbeatTimer = setInterval(() => {
            if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
                this.send({ type: 'ping', timestamp: Date.now() });
            }
        }, this.options.heartbeatInterval);
    }
    
    /**
     * Clear heartbeat timer
     */
    clearHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }
    
    /**
     * Get connection status
     * @returns {Object} Connection status info
     */
    getStatus() {
        return {
            connected: this.isConnected,
            readyState: this.ws ? this.ws.readyState : WebSocket.CLOSED,
            reconnectAttempts: this.reconnectAttempts,
            queuedMessages: this.messageQueue.length
        };
    }
    
    /**
     * Log debug messages
     * @param {...any} args - Arguments to log
     */
    log(...args) {
        if (this.options.debug) {
            console.log('[WebSocket]', ...args);
        }
    }
}

/**
 * SoulLink WebSocket Manager
 * Specialized WebSocket client for SoulLink Tracker
 */
class SoulLinkWebSocket {
    constructor(apiUrl, runId, options = {}) {
        this.apiUrl = apiUrl;
        this.runId = runId;
        
        // Don't build URL immediately - wait for connection attempt
        this.wsUrl = null;
        this.authError = null;
        
        this.client = new WebSocketClient('', {
            debug: true,
            ...options
        });
        
        this.stats = {
            encounters: 0,
            catches: 0,
            faints: 0,
            soulLinks: 0,
            lastEventTime: null
        };
        
        this.setupEventHandlers();
    }
    
    /**
     * Build WebSocket URL from API URL
     * @returns {string} WebSocket URL
     */
    buildWebSocketUrl() {
        const url = new URL(this.apiUrl);
        const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
        
        // Get session token from localStorage with improved error handling
        const sessionToken = this.retrieveBearerToken();
        if (!sessionToken) {
            console.error('No valid session token found. WebSocket connection will fail.');
            throw new Error('Authentication token required for WebSocket connection');
        }
        
        return `${wsProtocol}//${url.host}/v1/ws?run_id=${this.runId}&token=${encodeURIComponent(sessionToken)}`;
    }
    
    /**
     * Retrieve and validate session token from localStorage
     * @returns {string|null} Valid session token or null if not found/invalid
     */
    retrieveBearerToken() {
        // Priority order for session token retrieval
        const possibleKeys = [
            'soullink_session_token',    // New session token system (highest priority)
            'sessionToken',              // Alternative session token key
            'playerToken',               // Legacy Bearer token (fallback)
            'bearer_token',              // Legacy variations
            'authToken'
        ];
        
        for (const key of possibleKeys) {
            const savedToken = localStorage.getItem(key);
            if (!savedToken) continue;
            
            let extractedToken = null;
            
            // Handle plain token string
            if (typeof savedToken === 'string' && savedToken.length > 10) {
                extractedToken = savedToken.trim();
            }
            
            // Handle JSON format
            try {
                const tokenData = JSON.parse(savedToken);
                if (tokenData && tokenData.token && typeof tokenData.token === 'string') {
                    extractedToken = tokenData.token.trim();
                }
            } catch (e) {
                // Not JSON, use string value
            }
            
            // Validate token format
            if (extractedToken && extractedToken.length >= 10 && !extractedToken.includes(' ')) {
                console.log(`Found valid session token in localStorage key: ${key}`);
                return extractedToken;
            }
        }
        
        console.error('No valid session token found in localStorage. Available keys:',
                     Object.keys(localStorage).filter(k => k.toLowerCase().includes('token')));
        return null;
    }
    
    /**
     * Setup event handlers for SoulLink events
     */
    setupEventHandlers() {
        // Connection events
        this.client.on('connected', () => {
            console.log('Connected to SoulLink WebSocket');
            this.updateConnectionStatus(true);
        });
        
        this.client.on('disconnected', () => {
            console.log('Disconnected from SoulLink WebSocket');
            this.updateConnectionStatus(false);
        });
        
        this.client.on('reconnecting', (data) => {
            console.log(`Reconnecting to SoulLink WebSocket (attempt ${data.attempt})`);
            this.updateConnectionStatus(false, `Reconnecting (${data.attempt})...`);
        });
        
        this.client.on('auth_error', (error) => {
            console.error('SoulLink WebSocket authentication error:', error);
            this.updateConnectionStatus(false, 'Authentication Failed');
            Utils.showError('Authentication failed. Please check your login credentials or contact admin.');
        });
        
        this.client.on('error', (error) => {
            console.error('SoulLink WebSocket error:', error);
            if (error.type === 'connection_error') {
                Utils.showError('Connection error occurred. Check your login credentials.');
            } else {
                Utils.showError('Connection error occurred');
            }
        });
        
        // SoulLink-specific events
        this.client.on('encounter', (data) => {
            this.handleEncounterEvent(data);
        });
        
        this.client.on('catch_result', (data) => {
            this.handleCatchResultEvent(data);
        });
        
        this.client.on('faint', (data) => {
            this.handleFaintEvent(data);
        });
        
        this.client.on('soul_link', (data) => {
            this.handleSoulLinkEvent(data);
        });
        
        this.client.on('admin_override', (data) => {
            this.handleAdminEvent(data);
        });
        
        // Handle pong responses
        this.client.on('pong', (data) => {
            console.log('Received pong:', data);
        });
    }
    
    /**
     * Connect to WebSocket
     */
    connect() {
        // Build WebSocket URL at connection time to ensure Utils is available
        if (!this.wsUrl) {
            try {
                this.wsUrl = this.buildWebSocketUrl();
                console.log('WebSocket URL built successfully:', this.wsUrl);
            } catch (error) {
                console.error('Failed to build WebSocket URL:', error.message);
                this.authError = error.message;
                this.updateConnectionStatus(false, 'Authentication Error');
                
                // Show user-friendly error
                if (typeof Utils !== 'undefined' && Utils.showError) {
                    Utils.showError('Please log in to enable real-time updates. Visit the Player Setup page to enter your login credentials.');
                }
                return;
            }
        }
        
        // Update the client's URL
        this.client.url = this.wsUrl;
        
        if (!this.client) {
            console.error('Cannot connect: WebSocket client not initialized');
            this.updateConnectionStatus(false, 'Client Error');
            return;
        }
        
        this.client.connect();
    }
    
    /**
     * Disconnect from WebSocket
     */
    disconnect() {
        if (this.client) {
            this.client.disconnect();
        }
    }
    
    /**
     * Update connection status in UI
     * @param {boolean} connected - Connection status
     * @param {string} statusText - Status text override
     */
    updateConnectionStatus(connected, statusText = null) {
        const statusIndicator = document.getElementById('statusIndicator');
        const statusTextEl = document.getElementById('statusText');
        
        if (statusIndicator) {
            statusIndicator.className = `status-indicator ${connected ? 'connected' : 'disconnected'}`;
        }
        
        if (statusTextEl) {
            statusTextEl.textContent = statusText || (connected ? 'Connected' : 'Disconnected');
        }
    }
    
    /**
     * Handle encounter events
     * @param {Object} data - Event data
     */
    handleEncounterEvent(data) {
        console.log('Encounter event:', data);
        this.stats.encounters++;
        this.stats.lastEventTime = new Date();
        
        // Dispatch custom event for dashboard to handle
        document.dispatchEvent(new CustomEvent('soullink:encounter', { detail: data }));
        
        Utils.showSuccess(`New encounter: ${Utils.getPokemonName(data.data.species_id)} on ${Utils.getRouteName(data.data.route_id)}`);
    }
    
    /**
     * Handle catch result events
     * @param {Object} data - Event data
     */
    handleCatchResultEvent(data) {
        console.log('Catch result event:', data);
        
        if (data.data.status === 'caught') {
            this.stats.catches++;
            Utils.showSuccess(`Pokemon caught!`);
        }
        
        this.stats.lastEventTime = new Date();
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('soullink:catch_result', { detail: data }));
    }
    
    /**
     * Handle faint events
     * @param {Object} data - Event data
     */
    handleFaintEvent(data) {
        console.log('Faint event:', data);
        this.stats.faints++;
        this.stats.lastEventTime = new Date();
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('soullink:faint', { detail: data }));
        
        Utils.showError(`Pokemon fainted: ${data.data.pokemon_key}`);
    }
    
    /**
     * Handle soul link events
     * @param {Object} data - Event data
     */
    handleSoulLinkEvent(data) {
        console.log('Soul link event:', data);
        this.stats.soulLinks++;
        this.stats.lastEventTime = new Date();
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('soullink:soul_link', { detail: data }));
        
        Utils.showSuccess(`Soul link formed on ${Utils.getRouteName(data.data.route_id)}!`);
    }
    
    /**
     * Handle admin events
     * @param {Object} data - Event data
     */
    handleAdminEvent(data) {
        console.log('Admin event:', data);
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('soullink:admin', { detail: data }));
        
        Utils.showSuccess(`Admin action: ${Utils.snakeToTitle(data.data.action)}`);
    }
    
    /**
     * Get connection statistics
     * @returns {Object} Connection and event statistics
     */
    getStats() {
        return {
            ...this.stats,
            connectionStatus: this.client.getStatus()
        };
    }
    
    /**
     * Send message to server
     * @param {Object} message - Message to send
     */
    send(message) {
        this.client.send(message);
    }
    
    /**
     * Add event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    on(event, callback) {
        this.client.on(event, callback);
    }
    
    /**
     * Remove event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    off(event, callback) {
        this.client.off(event, callback);
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WebSocketClient, SoulLinkWebSocket };
}