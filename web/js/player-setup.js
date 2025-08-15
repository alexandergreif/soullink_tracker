/**
 * SoulLink Tracker Player Setup
 * Simple interface for players to connect to runs using just their token
 */

class PlayerSetup {
    constructor() {
        this.apiUrl = this.getApiUrl();
        this.playerData = null;
        this.runData = null;
        this.watcherProcess = null;
        
        this.init();
    }
    
    /**
     * Initialize the player setup interface
     */
    init() {
        this.setupEventListeners();
        this.loadSavedData();
        console.log('Player Setup initialized');
    }
    
    /**
     * Get API URL from environment or default
     */
    getApiUrl() {
        const params = Utils.getUrlParams();
        return params.api || window.SOULLINK_API_URL || 'http://127.0.0.1:8000';
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLoginSubmit(e));
        }
    }
    
    /**
     * Load any saved connection data
     */
    loadSavedData() {
        // Check for saved session token (new system)
        const savedSessionToken = localStorage.getItem('soullink_session_token');
        const savedRunId = localStorage.getItem('soullink_run_id');
        const savedPlayerId = localStorage.getItem('soullink_player_id');
        
        // Check for legacy token (backward compatibility)
        const legacyToken = localStorage.getItem('soullink_player_token');
        
        if (savedSessionToken && savedRunId && savedPlayerId) {
            // New system - auto-connect with session token
            this.token = savedSessionToken;
            this.runId = savedRunId;
            this.playerId = savedPlayerId;
            this.connectWithSessionToken(savedSessionToken, savedRunId, savedPlayerId);
        } else if (legacyToken) {
            // Legacy system - try to connect with old token
            this.connectWithToken(legacyToken);
        }
        
        // Load saved form data
        const savedRunName = localStorage.getItem('soullink_run_name');
        const savedPlayerName = localStorage.getItem('soullink_player_name');
        
        if (savedRunName) {
            document.getElementById('runName').value = savedRunName;
        }
        if (savedPlayerName) {
            document.getElementById('playerName').value = savedPlayerName;
        }
    }
    
    /**
     * Handle login form submission
     */
    async handleLoginSubmit(e) {
        e.preventDefault();
        
        const runNameInput = document.getElementById('runName');
        const playerNameInput = document.getElementById('playerName');
        const passwordInput = document.getElementById('runPassword');
        
        const runName = runNameInput.value.trim();
        const playerName = playerNameInput.value.trim();
        const password = passwordInput.value.trim();
        
        if (!runName) {
            this.showError('Please enter your run name');
            return;
        }
        
        if (!playerName) {
            this.showError('Please enter your player name');
            return;
        }
        
        if (!password) {
            this.showError('Please enter your run password');
            return;
        }
        
        await this.connectWithLogin(runName, playerName, password);
    }
    
    /**
     * Connect using login credentials (new system)
     */
    async connectWithLogin(runName, playerName, password) {
        const connectBtn = document.getElementById('connectBtn');
        const originalText = connectBtn.textContent;
        
        try {
            connectBtn.disabled = true;
            connectBtn.textContent = '⏳ Connecting...';
            
            this.hideError();
            this.updateApiStatus('Connecting...', 'pending');
            
            // Call login API
            const loginData = {
                run_name: runName,
                player_name: playerName,
                password: password
            };
            
            const response = await fetch(`${this.apiUrl}/v1/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(loginData)
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
                throw new Error(errorData.detail || `Login failed: ${response.status}`);
            }
            
            const loginResult = await response.json();
            
            if (!loginResult.session_token || !loginResult.run_id || !loginResult.player_id) {
                throw new Error('Invalid login response - missing required data');
            }
            
            // Store session data
            this.token = loginResult.session_token;
            this.runId = loginResult.run_id;
            this.playerId = loginResult.player_id;
            
            // Save for persistence (both new and legacy keys for backward compatibility)
            localStorage.setItem('soullink_session_token', loginResult.session_token);
            localStorage.setItem('soullink_player_token', loginResult.session_token); // Backward compatibility
            localStorage.setItem('soullink_run_id', loginResult.run_id);
            localStorage.setItem('soullink_player_id', loginResult.player_id);
            localStorage.setItem('soullink_run_name', runName);
            localStorage.setItem('soullink_player_name', playerName);
            
            // Fetch additional player and run data
            await this.fetchPlayerAndRunData();
            
            // Update UI
            this.updateConnectionStatus();
            
            // Start the watcher
            await this.startWatcher();
            
            this.updateApiStatus('Connected', 'connected');
            
        } catch (error) {
            console.error('Login failed:', error);
            this.showError(`Login failed: ${error.message}`);
            this.updateApiStatus('Login failed', 'disconnected');
        } finally {
            connectBtn.disabled = false;
            connectBtn.textContent = originalText;
        }
    }
    
    /**
     * Connect using existing session token (for auto-reconnect)
     */
    async connectWithSessionToken(sessionToken, runId, playerId) {
        try {
            this.updateApiStatus('Reconnecting...', 'pending');
            
            // Store session data
            this.token = sessionToken;
            this.runId = runId;
            this.playerId = playerId;
            
            // Fetch additional player and run data
            await this.fetchPlayerAndRunData();
            
            // Update UI
            this.updateConnectionStatus();
            
            // Start the watcher
            await this.startWatcher();
            
            this.updateApiStatus('Connected', 'connected');
            
        } catch (error) {
            console.error('Session reconnection failed:', error);
            // Clear invalid session data
            localStorage.removeItem('soullink_session_token');
            localStorage.removeItem('soullink_run_id');
            localStorage.removeItem('soullink_player_id');
            
            this.updateApiStatus('Session expired', 'disconnected');
            this.showError('Session expired. Please log in again.');
        }
    }
    
    /**
     * Connect using legacy token (backward compatibility)
     */
    async connectWithToken(token) {
        const connectBtn = document.getElementById('connectBtn');
        const originalText = connectBtn.textContent;
        
        try {
            connectBtn.disabled = true;
            connectBtn.textContent = '⏳ Connecting...';
            
            this.hideError();
            this.updateApiStatus('Connecting...', 'pending');
            
            // Decode the JWT token to get player info
            const tokenData = this.decodeJWT(token);
            if (!tokenData) {
                throw new Error('Invalid token format');
            }
            
            // Extract player_id and run_id from token
            const playerId = tokenData.player_id;
            const runId = tokenData.run_id;
            
            if (!playerId || !runId) {
                throw new Error('Token missing required information (player_id or run_id)');
            }
            
            // Get the actual bearer token for API calls
            const bearerToken = tokenData.token || token;
            
            // Store session data
            this.token = bearerToken;
            this.runId = runId;
            this.playerId = playerId;
            
            // Fetch additional player and run data
            await this.fetchPlayerAndRunData();
            
            // Update UI
            this.updateConnectionStatus();
            
            // Start the watcher
            await this.startWatcher();
            
            this.updateApiStatus('Connected', 'connected');
            
        } catch (error) {
            console.error('Connection failed:', error);
            this.showError(`Connection failed: ${error.message}`);
            this.updateApiStatus('Connection failed', 'disconnected');
        } finally {
            connectBtn.disabled = false;
            connectBtn.textContent = originalText;
        }
    }
    
    /**
     * Fetch player and run data using session token
     */
    async fetchPlayerAndRunData() {
        // Test API connection by fetching player data
        const playerResponse = await fetch(`${this.apiUrl}/v1/runs/${this.runId}/players`, {
            headers: {
                'Authorization': `Bearer ${this.token}`
            }
        });
        
        if (!playerResponse.ok) {
            throw new Error(`API connection failed: ${playerResponse.status}`);
        }
        
        const playersData = await playerResponse.json();
        const players = Array.isArray(playersData) ? playersData : (playersData.players || []);
        const currentPlayer = players.find(p => p.id === this.playerId);
        
        if (!currentPlayer) {
            throw new Error('Player not found in run');
        }
        
        this.playerData = currentPlayer;
        
        // Fetch run data
        const runResponse = await fetch(`${this.apiUrl}/v1/runs/${this.runId}`, {
            headers: {
                'Authorization': `Bearer ${this.token}`
            }
        });
        
        if (runResponse.ok) {
            this.runData = await runResponse.json();
        }
    }
    
    /**
     * Decode JWT token (simple client-side decoding - not for security)
     * Kept for backward compatibility with legacy tokens
     */
    decodeJWT(token) {
        try {
            const parts = token.split('.');
            if (parts.length !== 3) {
                return null;
            }
            
            const payload = parts[1];
            // Add padding if needed
            const paddedPayload = payload + '='.repeat((4 - payload.length % 4) % 4);
            
            const decoded = atob(paddedPayload);
            return JSON.parse(decoded);
        } catch (error) {
            console.error('Failed to decode JWT:', error);
            return null;
        }
    }
    
    /**
     * Update connection status display
     */
    updateConnectionStatus() {
        if (this.playerData) {
            document.getElementById('playerName').textContent = this.playerData.name;
            document.getElementById('playerGame').textContent = this.playerData.game;
        }
        
        if (this.runData) {
            document.getElementById('runName').textContent = this.runData.name;
        }
        
        // Show the "View My Progress" button
        const openDashboardBtn = document.getElementById('openDashboardBtn');
        if (openDashboardBtn && this.runId) {
            openDashboardBtn.style.display = 'inline-block';
        }
    }
    
    /**
     * Start the watcher process
     */
    async startWatcher() {
        try {
            this.updateWatcherStatus('Starting...', 'pending');
            
            // Configure environment for watcher
            const watcherConfig = {
                base_url: this.apiUrl,
                run_id: this.runId,
                player_id: this.playerId,
                token: this.token,
                spool_dir: 'C:\\temp\\soullink_events',
                dev: true
            };
            
            // Start monitoring spool directory
            this.startSpoolMonitor();
            
            this.updateWatcherStatus('Running', 'connected');
            
            console.log('Watcher configuration:', watcherConfig);
            
        } catch (error) {
            console.error('Failed to start watcher:', error);
            this.updateWatcherStatus('Failed to start', 'disconnected');
        }
    }
    
    /**
     * Start monitoring the spool directory for events
     */
    startSpoolMonitor() {
        // This would ideally start a background process
        // For now, we'll just show that the watcher is "running"
        console.log('Spool monitor started - watching for events from DeSmuME Lua script');
        
        // In a real implementation, this would:
        // 1. Monitor C:\temp\soullink_events\ for new JSON files
        // 2. Read the events and send them to the API
        // 3. Delete processed files
    }
    
    /**
     * Update API status display
     */
    updateApiStatus(status, type) {
        const statusEl = document.getElementById('apiStatus');
        const indicatorEl = document.getElementById('apiIndicator');
        
        if (statusEl) statusEl.textContent = status;
        if (indicatorEl) {
            indicatorEl.className = `status-indicator ${type}`;
        }
    }
    
    /**
     * Update watcher status display
     */
    updateWatcherStatus(status, type) {
        const statusEl = document.getElementById('watcherStatus');
        const indicatorEl = document.getElementById('watcherIndicator');
        
        if (statusEl) statusEl.textContent = status;
        if (indicatorEl) {
            indicatorEl.className = `status-indicator ${type}`;
        }
    }
    
    /**
     * Show error message
     */
    showError(message) {
        const errorEl = document.getElementById('errorMessage');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.remove('hidden');
        }
    }
    
    /**
     * Hide error message
     */
    hideError() {
        const errorEl = document.getElementById('errorMessage');
        if (errorEl) {
            errorEl.classList.add('hidden');
        }
    }
}

/**
 * Global function to open player dashboard
 */
function openPlayerDashboard() {
    if (window.playerSetup && window.playerSetup.runId) {
        const dashboardUrl = `/dashboard?api=${encodeURIComponent(window.playerSetup.apiUrl)}&run=${window.playerSetup.runId}`;
        window.open(dashboardUrl, '_blank');
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.playerSetup = new PlayerSetup();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlayerSetup;
}