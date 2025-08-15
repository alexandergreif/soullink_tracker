/**
 * SoulLink Tracker Admin Panel
 * Provides an intuitive admin interface for managing runs and players
 */

class AdminPanel {
    constructor() {
        this.apiUrl = this.getApiUrl();
        this.currentSection = 'runs';
        this.selectedRunId = null;
        this.runs = [];
        this.players = [];
        
        this.init();
    }
    
    /**
     * Get API URL from environment or default
     */
    getApiUrl() {
        const params = Utils.getUrlParams();
        return params.api || window.SOULLINK_API_URL || 'http://127.0.0.1:8000';
    }
    
    /**
     * Initialize the admin panel
     */
    async init() {
        try {
            this.setupEventListeners();
            await this.loadRuns();
            this.showSection('runs');
            await this.loadSystemStatus();
            console.log('Admin Panel initialized successfully');
        } catch (error) {
            console.error('Failed to initialize admin panel:', error);
            this.showError('Failed to initialize admin panel');
        }
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Navigation buttons
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const section = e.target.dataset.section;
                this.showSection(section);
            });
        });
        
        // Create run form
        const createRunForm = document.getElementById('createRunForm');
        if (createRunForm) {
            createRunForm.addEventListener('submit', (e) => this.handleCreateRun(e));
        }
        
        // Add player form
        const addPlayerForm = document.getElementById('addPlayerForm');
        if (addPlayerForm) {
            addPlayerForm.addEventListener('submit', (e) => this.handleAddPlayer(e));
        }
        
        // Run selection for players
        const runSelect = document.getElementById('runSelectForPlayers');
        if (runSelect) {
            runSelect.addEventListener('change', (e) => this.handleRunSelection(e));
        }
        
        // Modal close handlers
        const tokenModalClose = document.getElementById('tokenModalClose');
        if (tokenModalClose) {
            tokenModalClose.addEventListener('click', () => this.hideTokenModal());
        }
        
        // Toast close handlers
        const successToastClose = document.getElementById('successToastClose');
        const errorToastClose = document.getElementById('errorToastClose');
        
        if (successToastClose) {
            successToastClose.addEventListener('click', () => this.hideSuccessToast());
        }
        
        if (errorToastClose) {
            errorToastClose.addEventListener('click', () => this.hideErrorToast());
        }
        
        // Status refresh button
        const refreshStatusBtn = document.getElementById('refreshStatusBtn');
        if (refreshStatusBtn) {
            refreshStatusBtn.addEventListener('click', () => this.loadSystemStatus());
        }

        // Rebuild projections
        const rebuildProjectionsBtn = document.getElementById('rebuildProjectionsBtn');
        if (rebuildProjectionsBtn) {
            rebuildProjectionsBtn.addEventListener('click', () => this.handleRebuildProjections());
        }

        // Rebuild run selection
        const rebuildRunSelect = document.getElementById('rebuildRunSelect');
        if (rebuildRunSelect) {
            rebuildRunSelect.addEventListener('change', (e) => {
                const selected = e.target.value;
                document.getElementById('rebuildProjectionsBtn').disabled = !selected;
            });
        }

        // Player search and filters
        const playerSearchInput = document.getElementById('playerSearchInput');
        const searchPlayersBtn = document.getElementById('searchPlayersBtn');
        const gameFilterSelect = document.getElementById('gameFilterSelect');
        const statusFilterSelect = document.getElementById('statusFilterSelect');
        
        if (playerSearchInput) {
            playerSearchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.searchGlobalPlayers();
                }
            });
        }
        
        if (searchPlayersBtn) {
            searchPlayersBtn.addEventListener('click', () => this.searchGlobalPlayers());
        }
        
        if (gameFilterSelect) {
            gameFilterSelect.addEventListener('change', () => this.filterGlobalPlayers());
        }
        
        if (statusFilterSelect) {
            statusFilterSelect.addEventListener('change', () => this.filterGlobalPlayers());
        }

        // Settings section event listeners
        const refreshPlayerStats = document.getElementById('refreshPlayerStats');
        const refreshDbStatsBtn = document.getElementById('refreshDbStatsBtn');
        const refreshConnectionsBtn = document.getElementById('refreshConnectionsBtn');
        const validateDataBtn = document.getElementById('validateDataBtn');
        
        if (refreshPlayerStats) {
            refreshPlayerStats.addEventListener('click', () => this.loadPlayerStatistics());
        }
        
        if (refreshDbStatsBtn) {
            refreshDbStatsBtn.addEventListener('click', () => this.loadDatabaseStatistics());
        }
        
        if (refreshConnectionsBtn) {
            refreshConnectionsBtn.addEventListener('click', () => this.loadConnectionMonitoring());
        }
        
        if (validateDataBtn) {
            validateDataBtn.addEventListener('click', () => this.handleValidateData());
        }

        // Configuration update buttons
        const updateLogLevelBtn = document.getElementById('updateLogLevelBtn');
        const updateHeartbeatBtn = document.getElementById('updateHeartbeatBtn');
        const updateMaxPlayersBtn = document.getElementById('updateMaxPlayersBtn');
        
        if (updateLogLevelBtn) {
            updateLogLevelBtn.addEventListener('click', () => this.updateLogLevel());
        }
        
        if (updateHeartbeatBtn) {
            updateHeartbeatBtn.addEventListener('click', () => this.updateHeartbeatInterval());
        }
        
        if (updateMaxPlayersBtn) {
            updateMaxPlayersBtn.addEventListener('click', () => this.updateMaxPlayers());
        }

        // Quick action buttons
        const exportLogsBtn = document.getElementById('exportLogsBtn');
        const backupDatabaseBtn = document.getElementById('backupDatabaseBtn');
        const clearCacheBtn = document.getElementById('clearCacheBtn');
        
        if (exportLogsBtn) {
            exportLogsBtn.addEventListener('click', () => this.exportSystemLogs());
        }
        
        if (backupDatabaseBtn) {
            backupDatabaseBtn.addEventListener('click', () => this.backupDatabase());
        }
        
        if (clearCacheBtn) {
            clearCacheBtn.addEventListener('click', () => this.clearApplicationCache());
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideTokenModal();
            }
        });
        
        // API URL display
        const apiUrlDisplay = document.getElementById('apiUrlDisplay');
        if (apiUrlDisplay) {
            apiUrlDisplay.textContent = this.apiUrl;
        }
    }
    
    /**
     * Show specific admin section
     */
    showSection(sectionName) {
        // Update navigation
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.section === sectionName) {
                btn.classList.add('active');
            }
        });
        
        // Show/hide sections
        document.querySelectorAll('.admin-section').forEach(section => {
            section.classList.add('hidden');
        });
        
        const targetSection = document.getElementById(`${sectionName}Section`);
        if (targetSection) {
            targetSection.classList.remove('hidden');
        }
        
        this.currentSection = sectionName;
        
        // Load section-specific data
        if (sectionName === 'players') {
            this.populateRunSelect();
            this.loadPlayerStatistics();
            this.loadGlobalPlayers();
        } else if (sectionName === 'settings') {
            this.populateRebuildRunSelect();
            this.loadSystemStatus();
            this.loadDatabaseStatistics();
            this.loadConnectionMonitoring();
        }
    }
    
    /**
     * Load all runs from API
     */
    async loadRuns() {
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/runs`);
            if (!response.ok) {
                throw new Error(`Failed to load runs: ${response.status}`);
            }
            
            const data = await response.json();
            this.runs = Array.isArray(data) ? data : (data.runs || []);
            this.updateRunsList();
            
        } catch (error) {
            console.error('Error loading runs:', error);
            this.showError('Failed to load runs');
        }
    }
    
    /**
     * Update the runs list display
     */
    updateRunsList() {
        const runsList = document.getElementById('runsList');
        if (!runsList) return;
        
        runsList.innerHTML = '';
        
        if (this.runs.length === 0) {
            runsList.innerHTML = '<p class="text-muted">No runs created yet. Create your first run above!</p>';
            return;
        }
        
        this.runs.forEach(run => {
            const runCard = this.createRunCard(run);
            runsList.appendChild(runCard);
        });
    }
    
    /**
     * Create a run card element
     */
    createRunCard(run) {
        const card = document.createElement('div');
        card.className = 'admin-card';
        
        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <div>
                    <h4 style="margin: 0; color: var(--text-primary);">${this.escapeHtml(run.name)}</h4>
                    <p style="margin: 0.25rem 0 0 0; color: var(--text-muted); font-size: 0.875rem;">
                        Created: ${this.formatDate(run.created_at)}
                    </p>
                </div>
                <div style="display: flex; gap: 0.5rem;">
                    <button class="btn btn-secondary" onclick="adminPanel.viewRun('${run.id}')">
                        View Dashboard
                    </button>
                    <button class="btn btn-primary" onclick="adminPanel.manageRunPlayers('${run.id}')">
                        Manage Players
                    </button>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; font-size: 0.875rem;">
                <div>
                    <span style="color: var(--text-muted);">ID:</span><br>
                    <code style="font-size: 0.75rem; color: var(--text-secondary);">${run.id}</code>
                </div>
                <div>
                    <span style="color: var(--text-muted);">Max Players:</span><br>
                    <span style="color: var(--text-primary);">${run.rules_json?.max_players || 3}</span>
                </div>
                <div>
                    <span style="color: var(--text-muted);">Status:</span><br>
                    <span style="color: var(--success-color);">Active</span>
                </div>
            </div>
        `;
        
        return card;
    }
    
    /**
     * Handle create run form submission
     */
    async handleCreateRun(e) {
        e.preventDefault();
        
        const runName = document.getElementById('runNameInput').value;
        const maxPlayers = parseInt(document.getElementById('maxPlayersInput').value);
        const runPassword = document.getElementById('runPasswordInput').value;
        
        if (!runName.trim()) {
            this.showError('Please enter a run name');
            return;
        }
        
        if (!runPassword.trim()) {
            this.showError('Please enter a run password');
            return;
        }
        
        const createBtn = document.getElementById('createRunBtn');
        const originalText = createBtn.textContent;
        
        try {
            createBtn.disabled = true;
            createBtn.textContent = 'Creating...';
            
            const response = await fetch(`${this.apiUrl}/v1/admin/runs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: runName.trim(),
                    rules_json: {
                        max_players: maxPlayers
                    },
                    password: runPassword.trim()
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }
            
            const newRun = await response.json();
            
            // Reset form
            e.target.reset();
            
            // Reload runs
            await this.loadRuns();
            
            this.showSuccess(`Run "${newRun.name}" created successfully!`);
            
        } catch (error) {
            console.error('Error creating run:', error);
            this.showError(`Failed to create run: ${error.message}`);
        } finally {
            createBtn.disabled = false;
            createBtn.textContent = originalText;
        }
    }
    
    /**
     * Populate run select dropdown
     */
    populateRunSelect() {
        const runSelect = document.getElementById('runSelectForPlayers');
        if (!runSelect) return;
        
        runSelect.innerHTML = '<option value="">Select a run...</option>';
        
        this.runs.forEach(run => {
            const option = document.createElement('option');
            option.value = run.id;
            option.textContent = run.name;
            runSelect.appendChild(option);
        });
    }
    
    /**
     * Handle run selection for player management
     */
    async handleRunSelection(e) {
        const runId = e.target.value;
        
        if (!runId) {
            this.hidePlayerCards();
            return;
        }
        
        this.selectedRunId = runId;
        await this.loadPlayers(runId);
        this.showPlayerCards();
    }
    
    /**
     * Load players for a specific run
     */
    async loadPlayers(runId) {
        try {
            const response = await fetch(`${this.apiUrl}/v1/runs/${runId}/players`);
            if (!response.ok) {
                throw new Error(`Failed to load players: ${response.status}`);
            }
            
            const data = await response.json();
            this.players = Array.isArray(data) ? data : (data.players || []);
            this.updatePlayersList();
            
        } catch (error) {
            console.error('Error loading players:', error);
            this.showError('Failed to load players');
        }
    }
    
    /**
     * Show player management cards
     */
    showPlayerCards() {
        const addPlayerCard = document.getElementById('addPlayerCard');
        const playersListCard = document.getElementById('playersListCard');
        
        if (addPlayerCard) addPlayerCard.classList.remove('hidden');
        if (playersListCard) playersListCard.classList.remove('hidden');
    }
    
    /**
     * Hide player management cards
     */
    hidePlayerCards() {
        const addPlayerCard = document.getElementById('addPlayerCard');
        const playersListCard = document.getElementById('playersListCard');
        
        if (addPlayerCard) addPlayerCard.classList.add('hidden');
        if (playersListCard) playersListCard.classList.add('hidden');
        
        this.selectedRunId = null;
        this.players = [];
    }
    
    /**
     * Update the players list display
     */
    updatePlayersList() {
        const playersList = document.getElementById('currentPlayersList');
        if (!playersList) return;
        
        playersList.innerHTML = '';
        
        if (this.players.length === 0) {
            playersList.innerHTML = '<p class="text-muted">No players added yet. Add the first player above!</p>';
            return;
        }
        
        this.players.forEach(player => {
            const playerCard = this.createPlayerListItem(player);
            playersList.appendChild(playerCard);
        });
    }
    
    /**
     * Create a player list item
     */
    createPlayerListItem(player) {
        const item = document.createElement('div');
        item.className = 'admin-card';
        
        item.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="margin: 0; color: var(--text-primary);">${this.escapeHtml(player.name)}</h4>
                    <p style="margin: 0.25rem 0 0 0; color: var(--text-muted); font-size: 0.875rem;">
                        ${player.game} • ${player.region} • Created: ${this.formatDate(player.created_at)}
                    </p>
                </div>
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <button class="btn btn-small btn-primary" onclick="adminPanel.generateTokenForPlayer('${player.id}', '${this.escapeHtml(player.name)}')">
                        🔑 Get Token
                    </button>
                    <span style="color: var(--success-color); font-size: 0.875rem; font-weight: 500;">Active</span>
                </div>
            </div>
            <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--text-muted);">
                <strong>Player ID:</strong> <code>${player.id}</code>
            </div>
        `;
        
        return item;
    }
    
    /**
     * Handle add player form submission
     */
    async handleAddPlayer(e) {
        e.preventDefault();
        
        if (!this.selectedRunId) {
            this.showError('Please select a run first');
            return;
        }
        
        const playerName = document.getElementById('playerNameInput').value;
        const playerGame = document.getElementById('playerGameSelect').value;
        const playerRegion = document.getElementById('playerRegionInput').value;
        
        if (!playerName.trim()) {
            this.showError('Please enter a player name');
            return;
        }
        
        const addBtn = document.getElementById('addPlayerBtn');
        const originalText = addBtn.textContent;
        
        try {
            addBtn.disabled = true;
            addBtn.textContent = 'Adding...';
            
            const response = await fetch(`${this.apiUrl}/v1/admin/runs/${this.selectedRunId}/players`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: playerName.trim(),
                    game: playerGame,
                    region: playerRegion.trim()
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }
            
            const result = await response.json();
            
            // Reset form
            e.target.reset();
            document.getElementById('playerRegionInput').value = 'EU'; // Reset to default
            
            // Reload players
            await this.loadPlayers(this.selectedRunId);
            
            // Show token modal
            this.showTokenModal(result.player, result.token);
            
        } catch (error) {
            console.error('Error adding player:', error);
            this.showError(`Failed to add player: ${error.message}`);
        } finally {
            addBtn.disabled = false;
            addBtn.textContent = originalText;
        }
    }
    
    /**
     * Show token modal with player details
     */
    showTokenModal(player, token) {
        const modal = document.getElementById('tokenModal');
        const modalBody = document.getElementById('tokenModalBody');
        
        if (!modal || !modalBody) return;
        
        modalBody.innerHTML = `
            <div class="token-display">
                <div class="token-warning">
                    ⚠️ <strong>Important:</strong> Copy this token now! It will only be shown once and cannot be retrieved later.
                </div>
                
                <h4>Player Token Generated</h4>
                
                <div class="token-container">
                    <input type="text" class="token-input" value="${token}" readonly id="generatedToken">
                    <button class="copy-btn" onclick="adminPanel.copyToken()">Copy</button>
                </div>
                
                <div class="player-details">
                    <p><strong>Player:</strong> ${this.escapeHtml(player.name)}</p>
                    <p><strong>Game:</strong> ${player.game}</p>
                    <p><strong>Region:</strong> ${player.region}</p>
                    <p><strong>Player ID:</strong> <code>${player.id}</code></p>
                </div>
                
                <div style="margin-top: 1.5rem; text-align: center;">
                    <button class="btn btn-primary" onclick="adminPanel.hideTokenModal()">Done</button>
                </div>
            </div>
        `;
        
        modal.classList.add('show');
    }
    
    /**
     * Hide token modal
     */
    hideTokenModal() {
        const modal = document.getElementById('tokenModal');
        if (modal) {
            modal.classList.remove('show');
        }
    }
    
    /**
     * Copy token to clipboard
     */
    async copyToken() {
        const tokenInput = document.getElementById('generatedToken');
        if (!tokenInput) return;
        
        try {
            await navigator.clipboard.writeText(tokenInput.value);
            this.showSuccess('Token copied to clipboard!');
        } catch (error) {
            // Fallback for older browsers
            tokenInput.select();
            document.execCommand('copy');
            this.showSuccess('Token copied to clipboard!');
        }
    }
    
    /**
     * Generate token for existing player
     */
    async generateTokenForPlayer(playerId, playerName) {
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/players/${playerId}/token`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to generate token: ${response.status}`);
            }

            const result = await response.json();
            
            // Find the actual player data from the cached players array
            const actualPlayer = this.players.find(p => p.id === playerId);
            const player = {
                id: playerId,
                name: playerName,
                game: actualPlayer ? actualPlayer.game : 'Unknown',
                region: actualPlayer ? actualPlayer.region : 'Unknown'
            };
            
            // Show the token modal
            this.showTokenModal(player, result.bearer_token);
            
        } catch (error) {
            console.error('Error generating token:', error);
            this.showError(`Failed to generate token: ${error.message}`);
        }
    }
    
    /**
     * View run dashboard
     */
    viewRun(runId) {
        const dashboardUrl = `/dashboard?api=${encodeURIComponent(this.apiUrl)}&run=${runId}`;
        window.open(dashboardUrl, '_blank');
    }
    
    /**
     * Manage run players (switch to players section)
     */
    async manageRunPlayers(runId) {
        // Switch to players section
        this.showSection('players');
        
        // Select the run
        const runSelect = document.getElementById('runSelectForPlayers');
        if (runSelect) {
            runSelect.value = runId;
            await this.handleRunSelection({ target: { value: runId } });
        }
    }
    
    /**
     * Show success toast
     */
    showSuccess(message) {
        const toast = document.getElementById('successToast');
        const messageEl = document.getElementById('successMessage');
        
        if (toast && messageEl) {
            messageEl.textContent = message;
            toast.classList.add('show');
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                toast.classList.remove('show');
            }, 5000);
        }
    }
    
    /**
     * Show error toast
     */
    showError(message) {
        const toast = document.getElementById('errorToast');
        const messageEl = document.getElementById('errorMessage');
        
        if (toast && messageEl) {
            messageEl.textContent = message;
            toast.classList.add('show');
            
            // Auto-hide after 7 seconds
            setTimeout(() => {
                toast.classList.remove('show');
            }, 7000);
        }
    }
    
    /**
     * Hide success toast
     */
    hideSuccessToast() {
        const toast = document.getElementById('successToast');
        if (toast) {
            toast.classList.remove('show');
        }
    }
    
    /**
     * Hide error toast
     */
    hideErrorToast() {
        const toast = document.getElementById('errorToast');
        if (toast) {
            toast.classList.remove('show');
        }
    }
    
    /**
     * Format date for display
     */
    formatDate(dateStr) {
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        } catch (error) {
            return 'Unknown';
        }
    }
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Load player statistics
     */
    async loadPlayerStatistics() {
        try {
            const [playersResponse, runsResponse] = await Promise.all([
                fetch(`${this.apiUrl}/v1/admin/players/stats`),
                fetch(`${this.apiUrl}/v1/admin/runs`)
            ]);
            
            const playersData = await playersResponse.json().catch(() => ({ total: 0, active: 0, last_activity: null }));
            const runsData = await runsResponse.json().catch(() => []);
            
            // Update player statistics display
            const totalPlayers = document.getElementById('totalPlayersCount');
            const activePlayers = document.getElementById('activePlayersCount');
            const totalRuns = document.getElementById('totalRunsForPlayers');
            const lastActivity = document.getElementById('lastPlayerActivity');
            
            if (totalPlayers) totalPlayers.textContent = playersData.total || '0';
            if (activePlayers) activePlayers.textContent = playersData.active || '0';
            if (totalRuns) totalRuns.textContent = Array.isArray(runsData) ? runsData.length : '0';
            if (lastActivity) {
                lastActivity.textContent = playersData.last_activity
                    ? this.formatDate(playersData.last_activity)
                    : 'No activity yet';
            }
            
        } catch (error) {
            console.error('Error loading player statistics:', error);
            // Set fallback values
            ['totalPlayersCount', 'activePlayersCount', 'totalRunsForPlayers', 'lastPlayerActivity'].forEach(id => {
                const element = document.getElementById(id);
                if (element) element.textContent = 'Error';
            });
        }
    }
    
    /**
     * Load all players across all runs
     */
    async loadGlobalPlayers() {
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/players/global`);
            if (!response.ok) {
                throw new Error(`Failed to load global players: ${response.status}`);
            }
            
            const data = await response.json();
            this.globalPlayers = Array.isArray(data) ? data : (data.players || []);
            this.displayGlobalPlayers(this.globalPlayers);
            
        } catch (error) {
            console.error('Error loading global players:', error);
            this.displayGlobalPlayers([]);
        }
    }
    
    /**
     * Display global players list
     */
    displayGlobalPlayers(players) {
        const allPlayersList = document.getElementById('allPlayersList');
        if (!allPlayersList) return;
        
        allPlayersList.innerHTML = '';
        
        if (players.length === 0) {
            allPlayersList.innerHTML = '<p class="text-muted">No players found.</p>';
            return;
        }
        
        players.forEach(player => {
            const playerItem = this.createGlobalPlayerItem(player);
            allPlayersList.appendChild(playerItem);
        });
    }
    
    /**
     * Create a global player list item
     */
    createGlobalPlayerItem(player) {
        const item = document.createElement('div');
        item.className = 'global-player-item';
        
        const status = player.last_seen ? (Date.now() - new Date(player.last_seen) < 300000 ? 'Active' : 'Inactive') : 'Never connected';
        const statusClass = status === 'Active' ? 'success-color' : 'text-muted';
        
        item.innerHTML = `
            <div class="player-info">
                <div class="player-name">${this.escapeHtml(player.name)}</div>
                <div class="player-details">
                    Run: ${this.escapeHtml(player.run_name || 'Unknown')} •
                    Game: ${player.game} •
                    Region: ${player.region} •
                    Status: <span style="color: var(--${statusClass})">${status}</span>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
                    Created: ${this.formatDate(player.created_at)} •
                    ID: <code>${player.id}</code>
                </div>
            </div>
            <div class="player-actions">
                <button class="btn btn-small btn-primary" onclick="adminPanel.generateTokenForPlayer('${player.id}', '${this.escapeHtml(player.name)}')">
                    🔑 New Token
                </button>
                <button class="btn btn-small btn-secondary" onclick="adminPanel.viewPlayerRun('${player.run_id}')">
                    📊 View Run
                </button>
            </div>
        `;
        
        return item;
    }
    
    /**
     * Search global players
     */
    async searchGlobalPlayers() {
        const searchInput = document.getElementById('playerSearchInput');
        const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
        
        if (!query) {
            this.displayGlobalPlayers(this.globalPlayers || []);
            return;
        }
        
        const filtered = (this.globalPlayers || []).filter(player =>
            player.name.toLowerCase().includes(query) ||
            (player.run_name && player.run_name.toLowerCase().includes(query)) ||
            player.game.toLowerCase().includes(query) ||
            player.region.toLowerCase().includes(query)
        );
        
        this.displayGlobalPlayers(filtered);
    }
    
    /**
     * Filter global players
     */
    filterGlobalPlayers() {
        const gameFilter = document.getElementById('gameFilterSelect')?.value || '';
        const statusFilter = document.getElementById('statusFilterSelect')?.value || '';
        
        let filtered = this.globalPlayers || [];
        
        if (gameFilter) {
            filtered = filtered.filter(player => player.game === gameFilter);
        }
        
        if (statusFilter) {
            filtered = filtered.filter(player => {
                const isActive = player.last_seen && (Date.now() - new Date(player.last_seen) < 300000);
                return statusFilter === 'active' ? isActive : !isActive;
            });
        }
        
        this.displayGlobalPlayers(filtered);
    }
    
    /**
     * Load database statistics
     */
    async loadDatabaseStatistics() {
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/stats`);
            const stats = response.ok ? await response.json() : {};
            
            // Update database statistics display
            const totalRunsCount = document.getElementById('totalRunsCount');
            const totalPlayersInDb = document.getElementById('totalPlayersInDb');
            const totalEncounters = document.getElementById('totalEncounters');
            const activeConnections = document.getElementById('activeConnections');
            
            if (totalRunsCount) totalRunsCount.textContent = stats.total_runs || '0';
            if (totalPlayersInDb) totalPlayersInDb.textContent = stats.total_players || '0';
            if (totalEncounters) totalEncounters.textContent = stats.total_encounters || '0';
            if (activeConnections) activeConnections.textContent = stats.active_connections || '0';
            
        } catch (error) {
            console.error('Error loading database statistics:', error);
            // Set error state
            ['totalRunsCount', 'totalPlayersInDb', 'totalEncounters', 'activeConnections'].forEach(id => {
                const element = document.getElementById(id);
                if (element) element.textContent = 'Error';
            });
        }
    }
    
    /**
     * Load connection monitoring data
     */
    async loadConnectionMonitoring() {
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/connections`);
            const connections = response.ok ? await response.json() : { active: 0, total_data: 0, connections: [] };
            
            // Update connection monitoring display
            const wsConnectionCount = document.getElementById('wsConnectionCount');
            const dataTransferred = document.getElementById('dataTransferred');
            const connectionsList = document.getElementById('connectionsList');
            
            if (wsConnectionCount) wsConnectionCount.textContent = connections.active || '0';
            if (dataTransferred) {
                const dataKB = Math.round((connections.total_data || 0) / 1024);
                dataTransferred.textContent = `${dataKB} KB`;
            }
            
            // Update connections list
            if (connectionsList) {
                connectionsList.innerHTML = '';
                
                if (!connections.connections || connections.connections.length === 0) {
                    connectionsList.innerHTML = '<p class="text-muted" style="padding: 1rem;">No active connections</p>';
                } else {
                    connections.connections.forEach(conn => {
                        const connItem = document.createElement('div');
                        connItem.className = 'connection-item';
                        connItem.innerHTML = `
                            <div>
                                <strong>Player:</strong> ${this.escapeHtml(conn.player_name || 'Unknown')}<br>
                                <small>Run: ${this.escapeHtml(conn.run_name || 'Unknown')}</small>
                            </div>
                            <div style="text-align: right; font-size: 0.875rem; color: var(--text-muted);">
                                Connected: ${this.formatDate(conn.connected_at)}<br>
                                Data: ${Math.round((conn.data_transferred || 0) / 1024)} KB
                            </div>
                        `;
                        connectionsList.appendChild(connItem);
                    });
                }
            }
            
        } catch (error) {
            console.error('Error loading connection monitoring:', error);
            const wsConnectionCount = document.getElementById('wsConnectionCount');
            const dataTransferred = document.getElementById('dataTransferred');
            
            if (wsConnectionCount) wsConnectionCount.textContent = 'Error';
            if (dataTransferred) dataTransferred.textContent = 'Error';
        }
    }
    
    /**
     * Handle data validation
     */
    async handleValidateData() {
        const statusDiv = document.getElementById('validationStatus');
        
        try {
            statusDiv?.classList.remove('hidden');
            this.showValidationMessage('Validating data integrity...', 'info');
            
            const response = await fetch(`${this.apiUrl}/v1/admin/validate`, {
                method: 'POST',
            });
            
            if (response.ok) {
                const result = await response.json();
                const issues = result.issues || [];
                
                if (issues.length === 0) {
                    this.showValidationMessage('Data validation completed successfully. No issues found.', 'success');
                } else {
                    this.showValidationMessage(`Validation completed with ${issues.length} issues found. Check logs for details.`, 'error');
                }
            } else {
                const error = await response.json();
                this.showValidationMessage(`Validation failed: ${error.detail || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            console.error('Data validation error:', error);
            this.showValidationMessage('Validation failed: Network error', 'error');
        }
    }
    
    /**
     * Show validation message
     */
    showValidationMessage(message, type) {
        const statusDiv = document.getElementById('validationStatus');
        if (!statusDiv) return;
        
        statusDiv.className = `status-message ${type}`;
        statusDiv.textContent = message;
        statusDiv.classList.remove('hidden');
        
        if (type === 'success') {
            setTimeout(() => {
                statusDiv.classList.add('hidden');
            }, 5000);
        }
    }
    
    /**
     * Copy text to clipboard utility
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showSuccess('Copied to clipboard!');
        } catch (error) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showSuccess('Copied to clipboard!');
        }
    }
    
    /**
     * View player's run dashboard
     */
    viewPlayerRun(runId) {
        const dashboardUrl = `/dashboard?api=${encodeURIComponent(this.apiUrl)}&run=${runId}`;
        window.open(dashboardUrl, '_blank');
    }
    
    /**
     * Configuration update methods
     */
    async updateLogLevel() {
        const logLevelSelect = document.getElementById('logLevelSelect');
        const newLevel = logLevelSelect?.value;
        
        if (!newLevel) return;
        
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/config/log-level`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ level: newLevel })
            });
            
            if (response.ok) {
                this.showSuccess(`Log level updated to ${newLevel}`);
            } else {
                throw new Error('Failed to update log level');
            }
        } catch (error) {
            console.error('Error updating log level:', error);
            this.showError('Failed to update log level');
        }
    }
    
    async updateHeartbeatInterval() {
        const heartbeatInput = document.getElementById('heartbeatInterval');
        const newInterval = parseInt(heartbeatInput?.value);
        
        if (!newInterval || newInterval < 10 || newInterval > 300) {
            this.showError('Heartbeat interval must be between 10 and 300 seconds');
            return;
        }
        
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/config/heartbeat`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ interval: newInterval })
            });
            
            if (response.ok) {
                this.showSuccess(`Heartbeat interval updated to ${newInterval} seconds`);
            } else {
                throw new Error('Failed to update heartbeat interval');
            }
        } catch (error) {
            console.error('Error updating heartbeat interval:', error);
            this.showError('Failed to update heartbeat interval');
        }
    }
    
    async updateMaxPlayers() {
        const maxPlayersInput = document.getElementById('maxPlayersPerRun');
        const newMax = parseInt(maxPlayersInput?.value);
        
        if (!newMax || newMax < 2 || newMax > 10) {
            this.showError('Max players must be between 2 and 10');
            return;
        }
        
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/config/max-players`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ max_players: newMax })
            });
            
            if (response.ok) {
                this.showSuccess(`Max players per run updated to ${newMax}`);
            } else {
                throw new Error('Failed to update max players');
            }
        } catch (error) {
            console.error('Error updating max players:', error);
            this.showError('Failed to update max players');
        }
    }
    
    /**
     * Quick action methods
     */
    async exportSystemLogs() {
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/logs/export`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `soullink-logs-${new Date().toISOString().split('T')[0]}.zip`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                this.showSuccess('System logs exported successfully');
            } else {
                throw new Error('Failed to export logs');
            }
        } catch (error) {
            console.error('Error exporting logs:', error);
            this.showError('Failed to export system logs');
        }
    }
    
    async backupDatabase() {
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/database/backup`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showSuccess(`Database backup created: ${result.backup_file}`);
            } else {
                throw new Error('Failed to create database backup');
            }
        } catch (error) {
            console.error('Error creating database backup:', error);
            this.showError('Failed to create database backup');
        }
    }
    
    async clearApplicationCache() {
        if (!confirm('Are you sure you want to clear the application cache? This may temporarily impact performance.')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/cache/clear`, {
                method: 'POST'
            });
            
            if (response.ok) {
                this.showSuccess('Application cache cleared successfully');
            } else {
                throw new Error('Failed to clear cache');
            }
        } catch (error) {
            console.error('Error clearing cache:', error);
            this.showError('Failed to clear application cache');
        }
    }
}

// CSS for additional admin styles
const adminStyles = `
.admin-nav {
    display: flex;
    gap: 1rem;
    margin-bottom: 2rem;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 1rem;
}

.nav-btn {
    padding: 0.75rem 1.5rem;
    background: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-weight: 500;
}

.nav-btn:hover {
    background: var(--surface-hover);
    border-color: var(--border-accent);
    color: var(--text-primary);
}

.nav-btn.active {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
    box-shadow: 0 0 10px var(--glow-primary);
}

.admin-section.hidden {
    display: none;
}

.admin-card {
    background: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    margin-bottom: var(--spacing-lg);
    transition: all var(--transition-normal);
}

.admin-card:hover {
    border-color: var(--border-accent);
    box-shadow: 0 0 15px var(--glow-primary);
}

.admin-form {
    margin: 0;
}

.form-group {
    margin-bottom: var(--spacing-md);
}

.form-group label {
    display: block;
    color: var(--text-secondary);
    font-weight: 500;
    margin-bottom: var(--spacing-xs);
}

.form-group input,
.form-group select {
    width: 100%;
    padding: var(--spacing-sm);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background: var(--background-secondary);
    color: var(--text-primary);
    font-size: 0.9rem;
    transition: border-color var(--transition-fast);
}

.form-group input:focus,
.form-group select:focus {
    outline: none;
    border-color: var(--border-accent);
    box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.1);
}

.form-row {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr;
    gap: var(--spacing-md);
}

.info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--spacing-md);
}

.info-item {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
}

.info-item label {
    font-weight: 600;
    color: var(--text-secondary);
    font-size: 0.875rem;
}

.info-item span {
    color: var(--text-primary);
}

.action-buttons {
    display: flex;
    gap: var(--spacing-md);
    flex-wrap: wrap;
}

.text-muted {
    color: var(--text-muted);
    font-style: italic;
}

@media (max-width: 768px) {
    .admin-nav {
        flex-direction: column;
    }
    
    .form-row {
        grid-template-columns: 1fr;
    }
    
    .action-buttons {
        flex-direction: column;
    }
}
`;

// Inject additional styles
const styleSheet = document.createElement('style');
styleSheet.textContent = adminStyles;
document.head.appendChild(styleSheet);

// Global variable for onclick handlers
let adminPanel;

// Initialize admin panel - handle both DOMContentLoaded and late script loading
function initializeAdminPanel() {
    if (typeof AdminPanel !== 'undefined' && !window.adminPanel) {
        adminPanel = new AdminPanel();
        window.adminPanel = adminPanel; // Make it globally accessible
    }
}

// Try to initialize immediately if DOM is already ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAdminPanel);
} else {
    // DOM is already loaded, initialize immediately
    initializeAdminPanel();
}

// Add new methods to AdminPanel prototype
AdminPanel.prototype.loadSystemStatus = async function() {
    try {
        const [healthResponse, readyResponse] = await Promise.all([
            fetch(`${this.apiUrl}/health`),
            fetch(`${this.apiUrl}/ready`)
        ]);
        
        const healthData = await healthResponse.json();
        const readyData = await readyResponse.json();
        
        this.updateSystemStatus(healthData, readyData);
        this.updateApiInfo(healthData);
        
    } catch (error) {
        console.error('Failed to load system status:', error);
        this.updateSystemStatusError();
    }
};

AdminPanel.prototype.updateSystemStatus = function(healthData, readyData) {
    // Service status
    const serviceStatus = document.getElementById('serviceStatus');
    const serviceDot = serviceStatus?.querySelector('.status-dot');
    const serviceText = serviceStatus?.querySelector('.status-text');
    
    if (healthData.status === 'healthy') {
        serviceDot?.classList.add('healthy');
        serviceDot?.classList.remove('error', 'warning');
        if (serviceText) serviceText.textContent = 'Healthy';
    } else {
        serviceDot?.classList.add('error');
        serviceDot?.classList.remove('healthy', 'warning');
        if (serviceText) serviceText.textContent = 'Unhealthy';
    }
    
    // Database status
    const databaseStatus = document.getElementById('databaseStatus');
    const dbDot = databaseStatus?.querySelector('.status-dot');
    const dbText = databaseStatus?.querySelector('.status-text');
    
    if (readyData.checks?.database) {
        dbDot?.classList.add('healthy');
        dbDot?.classList.remove('error', 'warning');
        if (dbText) dbText.textContent = 'Connected';
    } else {
        dbDot?.classList.add('error');
        dbDot?.classList.remove('healthy', 'warning');
        if (dbText) dbText.textContent = 'Error';
    }
    
    // Config status
    const configStatus = document.getElementById('configStatus');
    const configDot = configStatus?.querySelector('.status-dot');
    const configText = configStatus?.querySelector('.status-text');
    
    if (readyData.checks?.config) {
        configDot?.classList.add('healthy');
        configDot?.classList.remove('error', 'warning');
        if (configText) configText.textContent = 'Loaded';
    } else {
        configDot?.classList.add('error');
        configDot?.classList.remove('healthy', 'warning');
        if (configText) configText.textContent = 'Error';
    }
    
    // Response time
    const responseTime = document.getElementById('responseTime');
    if (responseTime && readyData.response_time_ms) {
        responseTime.textContent = `${readyData.response_time_ms}ms`;
    }
};

AdminPanel.prototype.updateSystemStatusError = function() {
    const statusDots = document.querySelectorAll('.status-dot');
    const statusTexts = document.querySelectorAll('.status-text');
    
    statusDots.forEach(dot => {
        dot.classList.add('error');
        dot.classList.remove('healthy', 'warning');
    });
    
    statusTexts.forEach(text => {
        text.textContent = 'Error';
    });
};

AdminPanel.prototype.updateApiInfo = function(healthData) {
    const versionDisplay = document.getElementById('versionDisplay');
    const environmentDisplay = document.getElementById('environmentDisplay');
    const eventStoreStatus = document.getElementById('eventStoreStatus');
    
    if (versionDisplay && healthData.version) {
        versionDisplay.textContent = healthData.version;
    }
    
    if (environmentDisplay) {
        environmentDisplay.textContent = 'Production'; // Could be determined from API
    }
    
    if (eventStoreStatus) {
        eventStoreStatus.textContent = 'Enabled'; // Could check feature flag
    }
};

AdminPanel.prototype.populateRebuildRunSelect = function() {
    const select = document.getElementById('rebuildRunSelect');
    if (!select) return;
    
    // Clear existing options except the first one
    while (select.children.length > 1) {
        select.removeChild(select.lastChild);
    }
    
    // Add runs to select
    this.runs.forEach(run => {
        const option = document.createElement('option');
        option.value = run.id;
        option.textContent = run.name;
        select.appendChild(option);
    });
};

AdminPanel.prototype.handleRebuildProjections = async function() {
    const selectElement = document.getElementById('rebuildRunSelect');
    const runId = selectElement?.value;
    const statusDiv = document.getElementById('rebuildStatus');
    
    if (!runId) {
        this.showStatusMessage('Please select a run first', 'error');
        return;
    }
    
    try {
        statusDiv?.classList.remove('hidden');
        this.showStatusMessage('Rebuilding projections...', 'info');
        
        const response = await fetch(`${this.apiUrl}/v1/admin/runs/${runId}/rebuild-projections`, {
            method: 'POST',
        });
        
        if (response.ok) {
            const result = await response.json();
            this.showStatusMessage(`Projections rebuilt successfully. Processed ${result.events_processed || 0} events.`, 'success');
        } else {
            const error = await response.json();
            this.showStatusMessage(`Failed to rebuild projections: ${error.detail || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Rebuild projections error:', error);
        this.showStatusMessage('Failed to rebuild projections: Network error', 'error');
    }
};

AdminPanel.prototype.showStatusMessage = function(message, type) {
    const statusDiv = document.getElementById('rebuildStatus');
    if (!statusDiv) return;
    
    statusDiv.className = `status-message ${type}`;
    statusDiv.textContent = message;
    statusDiv.classList.remove('hidden');
    
    if (type === 'success') {
        setTimeout(() => {
            statusDiv.classList.add('hidden');
        }, 5000);
    }
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdminPanel;
}