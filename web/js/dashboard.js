/**
 * SoulLink Tracker Dashboard - Main Application
 * Manages the dashboard UI and real-time updates
 */

class SoulLinkDashboard {
    constructor() {
        this.apiUrl = this.getApiUrl();
        this.runId = this.getRunId();
        this.websocket = null;
        this.refreshInterval = null;
        this.eventHistory = [];
        this.maxEventHistory = 50;
        
        // Data cache
        this.cache = {
            runData: null,
            players: [],
            encounters: [],
            soulLinks: [],
            lastUpdate: null
        };
        
        this.init();
    }
    
    /**
     * Initialize the dashboard
     */
    async init() {
        try {
            this.showLoading(true);
            
            // Setup event listeners
            this.setupEventListeners();
            
            // Check if run ID is available
            if (!this.runId) {
                this.showLoading(false);
                if (!window.adminUI) {
                    window.adminUI = new AdminUI({ apiUrl: this.apiUrl });
                }
                window.adminUI.showSetup();
                return;
            }
            
            // Load initial data
            await this.loadInitialData();
            
            // Setup WebSocket connection
            this.setupWebSocket();
            
            // Start periodic refresh for non-real-time data
            this.startPeriodicRefresh();
            
            this.showLoading(false);
            
            console.log('SoulLink Dashboard initialized successfully');
        } catch (error) {
            console.error('Failed to initialize dashboard:', error);
            Utils.showError('Failed to initialize dashboard');
            this.showLoading(false);
        }
    }
    
    /**
     * Get API URL from environment or default
     * @returns {string} API URL
     */
    getApiUrl() {
        // Try to get from URL params, environment, or use default
        const params = Utils.getUrlParams();
        return params.api || window.SOULLINK_API_URL || 'http://127.0.0.1:9000';
    }
    
    /**
     * Get run ID from URL params or storage
     * @returns {string|null} Run ID
     */
    getRunId() {
        const params = Utils.getUrlParams();
        const runId = params.run || params.run_id || Utils.storage.get('currentRunId');
        
        if (runId && Utils.isValidUUID(runId)) {
            Utils.storage.set('currentRunId', runId);
            return runId;
        }
        
        return null;
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Modal close handlers
        const modal = document.getElementById('eventModal');
        const modalClose = document.getElementById('modalClose');
        
        if (modalClose) {
            modalClose.addEventListener('click', () => this.hideModal());
        }
        
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hideModal();
                }
            });
        }
        
        // Toast close handlers
        const errorToastClose = document.getElementById('toastClose');
        const successToastClose = document.getElementById('successToastClose');
        
        if (errorToastClose) {
            errorToastClose.addEventListener('click', () => {
                document.getElementById('errorToast').classList.remove('show');
            });
        }
        
        if (successToastClose) {
            successToastClose.addEventListener('click', () => {
                document.getElementById('successToast').classList.remove('show');
            });
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideModal();
            }
        });
        
        // Custom WebSocket events
        document.addEventListener('soullink:encounter', (e) => {
            this.handleRealtimeEncounter(e.detail);
        });
        
        document.addEventListener('soullink:catch_result', (e) => {
            this.handleRealtimeCatchResult(e.detail);
        });
        
        document.addEventListener('soullink:faint', (e) => {
            this.handleRealtimeFaint(e.detail);
        });
        
        document.addEventListener('soullink:soul_link', (e) => {
            this.handleRealtimeSoulLink(e.detail);
        });
        
        // Run selection event
        window.addEventListener('soullink:run_selected', (e) => {
            const runId = e.detail?.runId || e.detail;
            if (runId && Utils.isValidUUID(runId)) {
                this.switchRun(runId);
            }
        });
        
        // Visibility change - pause/resume when tab is hidden/visible
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.pauseUpdates();
            } else {
                this.resumeUpdates();
            }
        });
    }
    
    /**
     * Load initial data from API
     */
    async loadInitialData() {
        if (!this.runId) {
            console.warn('No run ID available for loading data');
            return;
        }
        
        try {
            // Ensure cache arrays are always initialized
            this.cache.players = this.cache.players || [];
            this.cache.encounters = this.cache.encounters || [];
            this.cache.soulLinks = this.cache.soulLinks || [];
            
            // Load run data
            const runResponse = await fetch(`${this.apiUrl}/v1/runs/${this.runId}`);
            if (!runResponse.ok) {
                throw new Error(`Failed to load run data: ${runResponse.status}`);
            }
            this.cache.runData = await runResponse.json();
            
            // Load players
            try {
                const playersResponse = await fetch(`${this.apiUrl}/v1/runs/${this.runId}/players`);
                if (playersResponse.ok) {
                    const playersData = await playersResponse.json();
                    this.cache.players = Array.isArray(playersData) ? playersData : (playersData.players || []);
                }
            } catch (error) {
                console.warn('Failed to load players:', error);
                this.cache.players = [];
            }
            
            // Load recent encounters
            try {
                const encountersResponse = await fetch(`${this.apiUrl}/v1/runs/${this.runId}/encounters?limit=20`);
                if (encountersResponse.ok) {
                    const encountersData = await encountersResponse.json();
                    this.cache.encounters = Array.isArray(encountersData) ? encountersData : (encountersData.encounters || []);
                }
            } catch (error) {
                console.warn('Failed to load encounters:', error);
                this.cache.encounters = [];
            }
            
            // Load soul links (skip if endpoint doesn't exist yet)
            try {
                const soulLinksResponse = await fetch(`${this.apiUrl}/v1/runs/${this.runId}/links`);
                if (soulLinksResponse.ok) {
                    const soulLinksData = await soulLinksResponse.json();
                    this.cache.soulLinks = Array.isArray(soulLinksData) ? soulLinksData : (soulLinksData.links || []);
                }
            } catch (error) {
                console.warn('Soul links endpoint not available:', error);
                this.cache.soulLinks = [];
            }
            
            this.cache.lastUpdate = new Date();
            
            // Update UI with loaded data
            this.updateUI();
            
        } catch (error) {
            console.error('Error loading initial data:', error);
            throw error;
        }
    }
    
    /**
     * Setup WebSocket connection
     */
    setupWebSocket() {
        if (!this.runId) return;
        
        this.websocket = new SoulLinkWebSocket(this.apiUrl, this.runId, {
            debug: true,
            reconnectInterval: 3000,
            maxReconnectAttempts: 10
        });
        
        this.websocket.connect();
    }
    
    /**
     * Start periodic refresh for non-real-time data
     */
    startPeriodicRefresh() {
        // Refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            this.refreshData();
        }, 30000);
    }
    
    /**
     * Refresh data from API
     */
    async refreshData() {
        try {
            // Only refresh if page is visible
            if (document.hidden) return;
            
            // Refresh players data (party status might change)
            const playersResponse = await fetch(`${this.apiUrl}/v1/runs/${this.runId}/players`);
            if (playersResponse.ok) {
                const data = await playersResponse.json();
                this.cache.players = Array.isArray(data) ? data : (data.players || []);
                this.updatePlayersUI();
            }
            
            this.cache.lastUpdate = new Date();
            
        } catch (error) {
            console.error('Error refreshing data:', error);
        }
    }
    
    /**
     * Update the entire UI
     */
    updateUI() {
        this.updateRunInfo();
        this.updateOverview();
        this.updatePlayersUI();
        this.updateEventsUI();
        this.updateSoulLinksUI();
    }
    
    /**
     * Update run information
     */
    updateRunInfo() {
        const runNameEl = document.getElementById('runName');
        if (runNameEl && this.cache.runData) {
            runNameEl.textContent = this.cache.runData.name;
        }
    }
    
    /**
     * Update overview statistics
     */
    updateOverview() {
        const totalEncountersEl = document.getElementById('totalEncounters');
        const totalCaughtEl = document.getElementById('totalCaught');
        const activeSoulLinksEl = document.getElementById('activeSoulLinks');
        const totalFaintedEl = document.getElementById('totalFainted');
        
        // Calculate statistics
        const stats = this.calculateStats();
        
        if (totalEncountersEl) totalEncountersEl.textContent = Utils.formatNumber(stats.encounters);
        if (totalCaughtEl) totalCaughtEl.textContent = Utils.formatNumber(stats.caught);
        if (activeSoulLinksEl) activeSoulLinksEl.textContent = Utils.formatNumber(stats.soulLinks);
        if (totalFaintedEl) totalFaintedEl.textContent = Utils.formatNumber(stats.fainted);
    }
    
    /**
     * Calculate statistics from cached data
     * @returns {Object} Statistics object
     */
    calculateStats() {
        const encounters = this.cache.encounters.length;
        const caught = this.cache.encounters.filter(e => e.status === 'caught').length;
        const soulLinks = this.cache.soulLinks.length;
        
        // Calculate fainted from players (this would need additional API endpoint)
        const fainted = 0; // Placeholder
        
        return { encounters, caught, soulLinks, fainted };
    }
    
    /**
     * Update players UI
     */
    updatePlayersUI() {
        const playersGrid = document.getElementById('playersGrid');
        if (!playersGrid) return;
        
        playersGrid.innerHTML = '';
        
        this.cache.players.forEach(player => {
            const playerCard = this.createPlayerCard(player);
            playersGrid.appendChild(playerCard);
        });
    }
    
    /**
     * Create player card element
     * @param {Object} player - Player data
     * @returns {HTMLElement} Player card element
     */
    createPlayerCard(player) {
        // Get player statistics
        const playerEncounters = this.cache.encounters.filter(e => e.player_id === player.id);
        const playerCaught = playerEncounters.filter(e => e.status === 'caught');
        
        // Mock party data (would come from API in real implementation)
        const partyPokemon = []; // Placeholder
        
        return Utils.createElement('div', { className: 'player-card' }, [
            Utils.createElement('div', { className: 'player-header' }, [
                Utils.createElement('div', {}, [
                    Utils.createElement('div', { className: 'player-name' }, player.name),
                    Utils.createElement('div', { className: 'player-game' }, player.game)
                ]),
                Utils.createElement('div', { className: 'player-status online' })
            ]),
            Utils.createElement('div', { className: 'player-stats' }, [
                Utils.createElement('div', { className: 'player-stat' }, [
                    Utils.createElement('div', { className: 'player-stat-value' }, playerEncounters.length.toString()),
                    Utils.createElement('div', { className: 'player-stat-label' }, 'Encounters')
                ]),
                Utils.createElement('div', { className: 'player-stat' }, [
                    Utils.createElement('div', { className: 'player-stat-value' }, playerCaught.length.toString()),
                    Utils.createElement('div', { className: 'player-stat-label' }, 'Caught')
                ]),
                Utils.createElement('div', { className: 'player-stat' }, [
                    Utils.createElement('div', { className: 'player-stat-value' }, '0'),
                    Utils.createElement('div', { className: 'player-stat-label' }, 'Fainted')
                ])
            ]),
            Utils.createElement('div', { className: 'player-party' }, [
                Utils.createElement('div', { className: 'party-title' }, 'Party'),
                Utils.createElement('div', { className: 'party-pokemon' }, 
                    partyPokemon.length > 0 
                        ? partyPokemon.map(p => Utils.createElement('div', { className: 'pokemon-badge' }, p.name))
                        : [Utils.createElement('div', { className: 'pokemon-badge' }, 'No party data')]
                )
            ])
        ]);
    }
    
    /**
     * Update events UI
     */
    updateEventsUI() {
        const eventsList = document.getElementById('eventsList');
        if (!eventsList) return;
        
        eventsList.innerHTML = '';
        
        // Combine cached encounters with event history from WebSocket
        const allEvents = [...this.cache.encounters, ...this.eventHistory]
            .sort((a, b) => new Date(b.timestamp || b.time) - new Date(a.timestamp || a.time))
            .slice(0, 20);
        
        if (allEvents.length === 0) {
            eventsList.appendChild(
                Utils.createElement('div', { className: 'events-empty' }, 
                    'No events yet. Start playing to see encounters and catches!')
            );
            return;
        }
        
        allEvents.forEach(event => {
            const eventItem = this.createEventItem(event);
            eventsList.appendChild(eventItem);
        });
    }
    
    /**
     * Create event item element
     * @param {Object} event - Event data
     * @returns {HTMLElement} Event item element
     */
    createEventItem(event) {
        const eventType = event.type || (event.status === 'caught' ? 'caught' : 'encounter');
        const timestamp = event.timestamp || event.time || new Date().toISOString();
        
        let title, description;
        
        switch (eventType) {
            case 'encounter':
                title = `Wild ${Utils.getPokemonName(event.species_id)} appeared!`;
                description = `Level ${event.level} on ${Utils.getRouteName(event.route_id)}`;
                break;
            case 'caught':
                title = `${Utils.getPokemonName(event.species_id)} was caught!`;
                description = `Level ${event.level} on ${Utils.getRouteName(event.route_id)}`;
                break;
            case 'faint':
                title = 'Pokemon fainted';
                description = event.pokemon_key || 'Unknown Pokemon';
                break;
            default:
                title = Utils.snakeToTitle(eventType);
                description = 'Event occurred';
        }
        
        const eventItem = Utils.createElement('div', { 
            className: 'event-item',
            data: { eventId: event.id }
        }, [
            Utils.createElement('div', { className: `event-icon ${eventType}` }, 
                Utils.getEventIcon(eventType)),
            Utils.createElement('div', { className: 'event-details' }, [
                Utils.createElement('div', { className: 'event-title' }, title),
                Utils.createElement('div', { className: 'event-description' }, description)
            ]),
            Utils.createElement('div', { className: 'event-time' }, 
                Utils.formatRelativeTime(timestamp))
        ]);
        
        // Add click handler for event details
        eventItem.addEventListener('click', () => {
            this.showEventDetails(event);
        });
        
        return eventItem;
    }
    
    /**
     * Update soul links UI
     */
    updateSoulLinksUI() {
        const soulLinksGrid = document.getElementById('soulLinksGrid');
        const soulLinksEmpty = document.getElementById('soulLinksEmpty');
        
        if (!soulLinksGrid || !soulLinksEmpty) return;
        
        if (this.cache.soulLinks.length === 0) {
            soulLinksGrid.style.display = 'none';
            soulLinksEmpty.style.display = 'block';
            return;
        }
        
        soulLinksGrid.style.display = 'grid';
        soulLinksEmpty.style.display = 'none';
        soulLinksGrid.innerHTML = '';
        
        this.cache.soulLinks.forEach(soulLink => {
            const soulLinkCard = this.createSoulLinkCard(soulLink);
            soulLinksGrid.appendChild(soulLinkCard);
        });
    }
    
    /**
     * Create soul link card element
     * @param {Object} soulLink - Soul link data
     * @returns {HTMLElement} Soul link card element
     */
    createSoulLinkCard(soulLink) {
        const members = soulLink.members || [];
        
        return Utils.createElement('div', { className: 'soul-link-card' }, [
            Utils.createElement('div', { className: 'soul-link-header' }, [
                Utils.createElement('div', { className: 'soul-link-route' }, 
                    Utils.getRouteName(soulLink.route_id)),
                Utils.createElement('div', { className: 'soul-link-icon' }, '🔗')
            ]),
            Utils.createElement('div', { className: 'soul-link-members' }, 
                members.map(member => 
                    Utils.createElement('div', { className: 'soul-link-member' }, [
                        Utils.createElement('div', { className: 'member-player' }, member.player_name),
                        Utils.createElement('div', { className: 'member-pokemon' }, 
                            Utils.getPokemonName(member.species_id)),
                        Utils.createElement('div', { className: 'member-status' })
                    ])
                )
            )
        ]);
    }
    
    /**
     * Handle real-time encounter events
     * @param {Object} data - Event data
     */
    handleRealtimeEncounter(data) {
        // Add to event history
        this.eventHistory.unshift({
            ...data.data,
            type: 'encounter',
            timestamp: data.timestamp || new Date().toISOString()
        });
        
        // Limit history size
        if (this.eventHistory.length > this.maxEventHistory) {
            this.eventHistory = this.eventHistory.slice(0, this.maxEventHistory);
        }
        
        // Update UI
        this.updateOverview();
        this.updateEventsUI();
    }
    
    /**
     * Handle real-time catch result events
     * @param {Object} data - Event data
     */
    handleRealtimeCatchResult(data) {
        // Add to event history
        this.eventHistory.unshift({
            ...data.data,
            type: 'catch_result',
            timestamp: data.timestamp || new Date().toISOString()
        });
        
        // Update UI
        this.updateOverview();
        this.updateEventsUI();
    }
    
    /**
     * Handle real-time faint events
     * @param {Object} data - Event data
     */
    handleRealtimeFaint(data) {
        // Add to event history
        this.eventHistory.unshift({
            ...data.data,
            type: 'faint',
            timestamp: data.timestamp || new Date().toISOString()
        });
        
        // Update UI
        this.updateOverview();
        this.updateEventsUI();
        this.updatePlayersUI(); // Party status might have changed
    }
    
    /**
     * Handle real-time soul link events
     * @param {Object} data - Event data
     */
    handleRealtimeSoulLink(data) {
        // Refresh soul links data
        this.refreshSoulLinks();
        
        // Add to event history
        this.eventHistory.unshift({
            ...data.data,
            type: 'soul_link',
            timestamp: data.timestamp || new Date().toISOString()
        });
        
        // Update UI
        this.updateOverview();
        this.updateEventsUI();
    }
    
    /**
     * Switch to a different run
     * @param {string} newRunId - The new run ID
     */
    async switchRun(newRunId) {
        try {
            console.log('Switching to run:', newRunId);
            
            // Pause current updates
            this.pauseUpdates();
            
            // Disconnect WebSocket if connected
            if (this.websocket) {
                this.websocket.disconnect();
            }
            
            // Update run ID
            this.runId = newRunId;
            
            // Persist to storage and update URL
            Utils.storage.set('currentRunId', newRunId);
            const url = new URL(window.location.href);
            url.searchParams.set('run', newRunId);
            window.history.replaceState({}, '', url.toString());
            
            // Show loading
            this.showLoading(true);
            
            // Hide setup section, show dashboard
            if (window.adminUI) {
                window.adminUI.hideSetup();
            }
            
            // Reload initial data
            await this.loadInitialData();
            
            // Reconnect WebSocket
            this.setupWebSocket();
            
            // Restart periodic refresh
            this.startPeriodicRefresh();
            
            this.showLoading(false);
            
            console.log('Successfully switched to run:', newRunId);
            
        } catch (error) {
            console.error('Error switching run:', error);
            Utils.showError('Failed to switch run');
            this.showLoading(false);
        }
    }
    
    /**
     * Refresh soul links from API
     */
    async refreshSoulLinks() {
        try {
            const response = await fetch(`${this.apiUrl}/v1/runs/${this.runId}/links`);
            if (response.ok) {
                const data = await response.json();
                this.cache.soulLinks = Array.isArray(data) ? data : (data.links || []);
                this.updateSoulLinksUI();
            }
        } catch (error) {
            console.error('Error refreshing soul links:', error);
        }
    }
    
    /**
     * Show event details modal
     * @param {Object} event - Event data
     */
    showEventDetails(event) {
        const modal = document.getElementById('eventModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBody');
        
        if (!modal || !modalTitle || !modalBody) return;
        
        modalTitle.textContent = 'Event Details';
        modalBody.innerHTML = '';
        
        // Create event details content
        const details = Utils.createElement('div', {}, [
            Utils.createElement('h4', {}, 'Event Information'),
            Utils.createElement('p', {}, `Type: ${Utils.snakeToTitle(event.type || 'encounter')}`),
            Utils.createElement('p', {}, `Time: ${Utils.formatTime(event.timestamp || event.time)}`),
        ]);
        
        if (event.species_id) {
            details.appendChild(Utils.createElement('p', {}, `Pokemon: ${Utils.getPokemonName(event.species_id)}`));
            details.appendChild(Utils.createElement('p', {}, `Level: ${event.level || 'Unknown'}`));
        }
        
        if (event.route_id) {
            details.appendChild(Utils.createElement('p', {}, `Location: ${Utils.getRouteName(event.route_id)}`));
        }
        
        if (event.method) {
            details.appendChild(Utils.createElement('p', {}, `Method: ${Utils.snakeToTitle(event.method)}`));
        }
        
        modalBody.appendChild(details);
        modal.classList.add('show');
    }
    
    /**
     * Hide event details modal
     */
    hideModal() {
        const modal = document.getElementById('eventModal');
        if (modal) {
            modal.classList.remove('show');
        }
    }
    
    /**
     * Show/hide loading overlay
     * @param {boolean} show - Whether to show loading
     */
    showLoading(show) {
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.classList.toggle('hidden', !show);
        }
    }
    
    /**
     * Pause updates when tab is hidden
     */
    pauseUpdates() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    /**
     * Resume updates when tab becomes visible
     */
    resumeUpdates() {
        if (!this.refreshInterval) {
            this.startPeriodicRefresh();
            this.refreshData(); // Immediately refresh data
        }
    }
    
    /**
     * Cleanup resources
     */
    destroy() {
        if (this.websocket) {
            this.websocket.disconnect();
        }
        
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        // Remove event listeners
        document.removeEventListener('soullink:encounter', this.handleRealtimeEncounter);
        document.removeEventListener('soullink:catch_result', this.handleRealtimeCatchResult);
        document.removeEventListener('soullink:faint', this.handleRealtimeFaint);
        document.removeEventListener('soullink:soul_link', this.handleRealtimeSoulLink);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.soulLinkDashboard = new SoulLinkDashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.soulLinkDashboard) {
        window.soulLinkDashboard.destroy();
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SoulLinkDashboard;
}