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
            blocklist: [],
            lastUpdate: null
        };
        
        // Session data
        this.sessionData = this.getSessionData();
        
        // Filter states
        this.filters = {
            timeline: {
                type: 'all',
                player: 'all'
            },
            blocklist: {
                reason: 'all'
            }
        };
        
        this.init();
    }
    
    /**
     * Initialize the dashboard
     */
    async init() {
        try {
            this.showLoading(true);
            
            // Ensure admin controls are always visible
            this.ensureAdminControls();
            
            // Check authentication first
            if (!this.checkAuthentication()) {
                this.showLoading(false);
                return;
            }
            
            // Initialize auth status
            this.updateTokenStatus();
            
            // Setup event listeners
            this.setupEventListeners();
            
            // Check if run ID is available
            if (!this.runId) {
                this.showLoading(false);
                // Show run selector instead of admin setup
                await this.showRunSelector();
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
            this.showLoading(false);
            
            // Still ensure admin controls are visible even on error
            this.ensureAdminControls();
        }
    }
    
    /**
     * Update authentication status indicator
     */
    updateTokenStatus() {
        const tokenStatusDot = document.getElementById('tokenStatusDot');
        const tokenStatusText = document.getElementById('tokenStatusText');
        const configureBtn = document.getElementById('configureTokenBtn');
        
        if (!tokenStatusDot || !tokenStatusText || !configureBtn) return;
        
        const sessionData = this.getSessionData();
        
        if (sessionData.sessionToken && sessionData.runId && sessionData.playerId) {
            // Valid session exists
            tokenStatusDot.className = 'status-dot healthy';
            tokenStatusText.textContent = `Logged in as ${sessionData.playerName || 'Player'} (${sessionData.runName || 'Run'})`;
            configureBtn.textContent = 'Logout';
            configureBtn.onclick = () => this.logout();
        } else {
            // No valid session
            tokenStatusDot.className = 'status-dot error';
            tokenStatusText.textContent = 'Not logged in';
            configureBtn.textContent = 'Login';
            configureBtn.onclick = () => this.redirectToPlayerSetup();
        }
    }
    
    /**
     * Ensure admin controls are visible in the header
     */
    ensureAdminControls() {
        const headerInfo = document.querySelector('.header-info');
        let adminControls = document.querySelector('.admin-controls');
        
        if (!headerInfo) return;
        
        if (!adminControls) {
            // Create admin controls if they don't exist
            adminControls = document.createElement('div');
            adminControls.className = 'admin-controls';
            adminControls.innerHTML = `
                <button class="btn btn-secondary" onclick="window.open('/admin', '_blank')" title="Open Admin Panel">
                    ⚙️ Admin
                </button>
                <button class="btn btn-primary" onclick="window.showRunSelector()" title="Switch to different run">
                    🔄 Switch Run
                </button>
            `;
            
            // Insert as the first child of header-info
            headerInfo.insertBefore(adminControls, headerInfo.firstChild);
        }
        
        // Ensure they're visible
        adminControls.style.display = 'flex';
    }
    
    /**
     * Get API URL from environment or default
     * @returns {string} API URL
     */
    getApiUrl() {
        // Try to get from URL params, environment, or use default
        const params = Utils.getUrlParams();
        return params.api || window.SOULLINK_API_URL || 'http://127.0.0.1:8000';
    }
    
    /**
     * Get run ID from URL params or session storage
     * @returns {string|null} Run ID
     */
    getRunId() {
        const params = Utils.getUrlParams();
        const runId = params.run || params.run_id || localStorage.getItem('soullink_run_id') || Utils.storage.get('currentRunId');
        
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
        
        // Setup filter event listeners for new components
        this.setupFilterEventListeners();
        
        // Run selector modal handlers
        const runSelectorClose = document.getElementById('runSelectorClose');
        const switchToRunBtn = document.getElementById('switchToRunBtn');
        
        if (runSelectorClose) {
            runSelectorClose.addEventListener('click', () => this.hideRunSelector());
        }
        
        if (switchToRunBtn) {
            switchToRunBtn.addEventListener('click', () => this.handleSwitchToRun());
        }
        
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
            
            // Load blocklist
            try {
                const blocklistResponse = await fetch(`${this.apiUrl}/v1/runs/${this.runId}/blocklist`);
                if (blocklistResponse.ok) {
                    const blocklistData = await blocklistResponse.json();
                    this.cache.blocklist = Array.isArray(blocklistData) ? blocklistData : (blocklistData.blocked_families || []);
                }
            } catch (error) {
                console.warn('Blocklist endpoint not available:', error);
                this.cache.blocklist = [];
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
        this.updateBlocklistUI();
        this.updateTimelineUI();
        this.setupFilterEventListeners();
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
     * Update blocklist UI
     */
    updateBlocklistUI() {
        const blocklistGrid = document.getElementById('blocklistGrid');
        const blocklistEmpty = document.getElementById('blocklistEmpty');
        const blocklistCount = document.getElementById('blocklistCount');
        
        if (!blocklistGrid || !blocklistEmpty) return;
        
        // Update count
        if (blocklistCount) {
            blocklistCount.textContent = this.cache.blocklist.length;
        }
        
        if (this.cache.blocklist.length === 0) {
            blocklistGrid.style.display = 'none';
            blocklistEmpty.style.display = 'block';
            return;
        }
        
        blocklistGrid.style.display = 'grid';
        blocklistEmpty.style.display = 'none';
        
        // Apply current filter
        const filter = document.getElementById('blocklistFilter')?.value || 'all';
        const filteredBlocklist = this.filterBlocklist(this.cache.blocklist, filter);
        
        blocklistGrid.innerHTML = '';
        
        filteredBlocklist.forEach(entry => {
            const blocklistCard = this.createBlocklistCard(entry);
            blocklistGrid.appendChild(blocklistCard);
        });
    }
    
    /**
     * Filter blocklist by type
     * @param {Array} blocklist - Blocklist entries
     * @param {string} filter - Filter type
     * @returns {Array} Filtered blocklist
     */
    filterBlocklist(blocklist, filter) {
        if (filter === 'all') return blocklist;
        return blocklist.filter(entry => entry.origin === filter);
    }
    
    /**
     * Create blocklist card element
     * @param {Object} entry - Blocklist entry
     * @returns {HTMLElement} Blocklist card element
     */
    createBlocklistCard(entry) {
        const speciesBadges = entry.species_names?.map(name => 
            Utils.createElement('span', { className: 'blocked-species-badge' }, name)
        ) || [];
        
        return Utils.createElement('div', { className: 'blocked-family-card' }, [
            Utils.createElement('div', { className: 'blocked-family-header' }, [
                Utils.createElement('div', { className: 'blocked-family-id' }, 
                    `Family #${entry.family_id}`),
                Utils.createElement('span', { 
                    className: `blocked-family-origin ${entry.origin}` 
                }, entry.origin)
            ]),
            Utils.createElement('div', { className: 'blocked-species-list' }, speciesBadges),
            Utils.createElement('div', { className: 'blocked-family-time' }, 
                Utils.formatRelativeTime(entry.created_at))
        ]);
    }
    
    /**
     * Update timeline UI
     */
    updateTimelineUI() {
        const timelineContent = document.getElementById('timelineContent');
        const timelineCount = document.getElementById('timelineCount');
        
        if (!timelineContent) return;
        
        // Combine cached encounters with event history from WebSocket
        const allEvents = [...this.cache.encounters, ...this.eventHistory]
            .sort((a, b) => new Date(b.timestamp || b.time) - new Date(a.timestamp || a.time));
        
        // Apply current filters
        const eventFilter = document.getElementById('timelineFilter')?.value || 'all';
        const playerFilter = document.getElementById('timelinePlayer')?.value || 'all';
        
        const filteredEvents = this.filterTimelineEvents(allEvents, eventFilter, playerFilter);
        
        // Update count
        if (timelineCount) {
            timelineCount.textContent = filteredEvents.length;
        }
        
        timelineContent.innerHTML = '';
        
        if (filteredEvents.length === 0) {
            timelineContent.appendChild(
                Utils.createElement('div', { className: 'events-empty' }, 
                    'No events match the current filters.')
            );
            return;
        }
        
        // Limit to 50 events for performance
        const limitedEvents = filteredEvents.slice(0, 50);
        
        limitedEvents.forEach(event => {
            const timelineEvent = this.createTimelineEvent(event);
            timelineContent.appendChild(timelineEvent);
        });
    }
    
    /**
     * Filter timeline events
     * @param {Array} events - All events
     * @param {string} eventFilter - Event type filter
     * @param {string} playerFilter - Player filter
     * @returns {Array} Filtered events
     */
    filterTimelineEvents(events, eventFilter, playerFilter) {
        let filtered = events;
        
        // Filter by event type
        if (eventFilter !== 'all') {
            filtered = filtered.filter(event => {
                const eventType = event.type || (event.status === 'caught' ? 'caught' : 'encounter');
                return eventType === eventFilter;
            });
        }
        
        // Filter by player
        if (playerFilter !== 'all') {
            filtered = filtered.filter(event => event.player_id === playerFilter);
        }
        
        return filtered;
    }
    
    /**
     * Create timeline event element
     * @param {Object} event - Event data
     * @returns {HTMLElement} Timeline event element
     */
    createTimelineEvent(event) {
        const eventType = event.type || (event.status === 'caught' ? 'caught' : 'encounter');
        const timestamp = event.timestamp || event.time || new Date().toISOString();
        const player = this.cache.players.find(p => p.id === event.player_id);
        
        let title, description;
        
        switch (eventType) {
            case 'encounter':
                title = `Wild ${Utils.getPokemonName(event.species_id)} appeared!`;
                description = `Level ${event.level} • ${Utils.getRouteName(event.route_id)}`;
                if (event.method) {
                    description += ` • ${Utils.snakeToTitle(event.method)}`;
                }
                if (event.shiny) {
                    description += ' • ✨ Shiny';
                }
                break;
            case 'caught':
                title = `${Utils.getPokemonName(event.species_id)} was caught!`;
                description = `Level ${event.level} • ${Utils.getRouteName(event.route_id)}`;
                if (event.shiny) {
                    description += ' • ✨ Shiny';
                }
                break;
            case 'faint':
                title = 'Pokemon fainted';
                description = event.pokemon_key || 'Unknown Pokemon';
                break;
            default:
                title = Utils.snakeToTitle(eventType);
                description = 'Event occurred';
        }
        
        const timelineEvent = Utils.createElement('div', { 
            className: `timeline-event ${eventType}`,
            data: { eventId: event.id }
        }, [
            Utils.createElement('div', { className: 'timeline-event-time' }, 
                new Date(timestamp).toLocaleTimeString([], { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                })
            ),
            Utils.createElement('div', { className: `timeline-event-icon ${eventType}` }, 
                Utils.getEventIcon(eventType)
            ),
            Utils.createElement('div', { className: 'timeline-event-details' }, [
                Utils.createElement('div', { className: 'timeline-event-title' }, title),
                Utils.createElement('div', { className: 'timeline-event-description' }, description)
            ]),
            Utils.createElement('div', { className: 'timeline-event-player' }, 
                player?.name || 'Unknown Player')
        ]);
        
        // Add click handler for event details
        timelineEvent.addEventListener('click', () => {
            this.showEventDetails(event);
        });
        
        return timelineEvent;
    }
    
    /**
     * Setup filter event listeners
     */
    setupFilterEventListeners() {
        const blocklistFilter = document.getElementById('blocklistFilter');
        const timelineFilter = document.getElementById('timelineFilter');
        const timelinePlayer = document.getElementById('timelinePlayer');
        
        if (blocklistFilter && !blocklistFilter.hasAttribute('data-listener-added')) {
            blocklistFilter.addEventListener('change', () => {
                this.updateBlocklistUI();
            });
            blocklistFilter.setAttribute('data-listener-added', 'true');
        }
        
        if (timelineFilter && !timelineFilter.hasAttribute('data-listener-added')) {
            timelineFilter.addEventListener('change', () => {
                this.updateTimelineUI();
            });
            timelineFilter.setAttribute('data-listener-added', 'true');
        }
        
        if (timelinePlayer && !timelinePlayer.hasAttribute('data-listener-added')) {
            timelinePlayer.addEventListener('change', () => {
                this.updateTimelineUI();
            });
            timelinePlayer.setAttribute('data-listener-added', 'true');
            
            // Populate player options
            this.updatePlayerFilterOptions();
        }
    }
    
    /**
     * Update player filter options
     */
    updatePlayerFilterOptions() {
        const timelinePlayer = document.getElementById('timelinePlayer');
        if (!timelinePlayer) return;
        
        // Save current selection
        const currentValue = timelinePlayer.value;
        
        // Clear existing options except "All Players"
        timelinePlayer.innerHTML = '<option value="all">All Players</option>';
        
        // Add player options
        this.cache.players.forEach(player => {
            const option = document.createElement('option');
            option.value = player.id;
            option.textContent = player.name;
            timelinePlayer.appendChild(option);
        });
        
        // Restore selection if still valid
        if (currentValue && timelinePlayer.querySelector(`option[value="${currentValue}"]`)) {
            timelinePlayer.value = currentValue;
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
     * Show run selector modal
     */
    async showRunSelector() {
        const modal = document.getElementById('runSelectorModal');
        const runSelect = document.getElementById('runSelectModal');
        
        if (!modal || !runSelect) return;
        
        // Load available runs
        try {
            const response = await fetch(`${this.apiUrl}/v1/admin/runs`);
            if (response.ok) {
                const runs = await response.json();
                
                runSelect.innerHTML = '<option value="">Select a run...</option>';
                runs.forEach(run => {
                    const option = document.createElement('option');
                    option.value = run.id;
                    option.textContent = run.name;
                    if (run.id === this.runId) {
                        option.textContent += ' (current)';
                        option.selected = true;
                    }
                    runSelect.appendChild(option);
                });
            } else {
                runSelect.innerHTML = '<option value="">Failed to load runs</option>';
            }
        } catch (error) {
            console.error('Error loading runs:', error);
            runSelect.innerHTML = '<option value="">Error loading runs</option>';
        }
        
        modal.classList.add('show');
    }
    
    /**
     * Hide run selector modal
     */
    hideRunSelector() {
        const modal = document.getElementById('runSelectorModal');
        if (modal) {
            modal.classList.remove('show');
        }
    }
    
    /**
     * Handle switching to selected run
     */
    handleSwitchToRun() {
        const runSelect = document.getElementById('runSelectModal');
        if (!runSelect || !runSelect.value) {
            return;
        }
        
        const selectedRunId = runSelect.value;
        if (selectedRunId === this.runId) {
            this.hideRunSelector();
            return;
        }
        
        this.switchRun(selectedRunId);
        this.hideRunSelector();
    }
    
    /**
     * Check if user is authenticated and redirect if not
     * @returns {boolean} Whether user is authenticated
     */
    checkAuthentication() {
        const sessionData = this.getSessionData();
        
        if (!sessionData.sessionToken || !sessionData.runId || !sessionData.playerId) {
            // No valid session - redirect to player setup
            console.log('No valid session found, redirecting to player setup');
            this.redirectToPlayerSetup();
            return false;
        }
        
        return true;
    }
    
    /**
     * Get session data from localStorage
     * @returns {Object} Session data object
     */
    getSessionData() {
        return {
            sessionToken: localStorage.getItem('soullink_session_token') || localStorage.getItem('sessionToken'),
            runId: localStorage.getItem('soullink_run_id'),
            playerId: localStorage.getItem('soullink_player_id'),
            runName: localStorage.getItem('soullink_run_name'),
            playerName: localStorage.getItem('soullink_player_name')
        };
    }
    
    /**
     * Redirect to player setup page
     */
    redirectToPlayerSetup() {
        const currentUrl = new URL(window.location.href);
        const apiParam = currentUrl.searchParams.get('api');
        
        let playerUrl = '/player.html';
        if (apiParam) {
            playerUrl += `?api=${encodeURIComponent(apiParam)}`;
        }
        
        window.location.href = playerUrl;
    }
    
    /**
     * Logout and clear session data
     */
    logout() {
        // Clear all session data
        localStorage.removeItem('soullink_session_token');
        localStorage.removeItem('sessionToken');
        localStorage.removeItem('soullink_run_id');
        localStorage.removeItem('soullink_player_id');
        localStorage.removeItem('soullink_run_name');
        localStorage.removeItem('soullink_player_name');
        localStorage.removeItem('soullink_player_token'); // Legacy
        
        // Redirect to player setup
        this.redirectToPlayerSetup();
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
    
    /**
     * Setup filter event listeners for timeline and blocklist
     */
    setupFilterEventListeners() {
        // Timeline filter buttons
        document.querySelectorAll('.timeline-filters .filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filter = e.target.dataset.filter;
                this.filters.timeline.type = filter;
                
                // Update active button
                e.target.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                
                this.updateTimelineUI();
            });
        });
        
        // Player filter select
        const playerFilter = document.getElementById('playerFilter');
        if (playerFilter) {
            playerFilter.addEventListener('change', (e) => {
                this.filters.timeline.player = e.target.value;
                this.updateTimelineUI();
            });
        }
        
        // Blocklist filter buttons
        document.querySelectorAll('.blocklist-filters .filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filter = e.target.dataset.filter;
                this.filters.blocklist.reason = filter;
                
                // Update active button
                e.target.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                
                this.updateBlocklistUI();
            });
        });
    }
    
    /**
     * Update timeline UI with filtered events
     */
    updateTimelineUI() {
        const timelineList = document.getElementById('timelineList');
        const timelineEmpty = document.getElementById('timelineEmpty');
        
        if (!timelineList) return;
        
        // Filter encounters based on current filters
        const filteredEvents = this.filterTimelineEvents();
        
        if (filteredEvents.length === 0) {
            timelineList.style.display = 'none';
            timelineEmpty.style.display = 'block';
            return;
        }
        
        timelineList.style.display = 'block';
        timelineEmpty.style.display = 'none';
        
        // Sort by timestamp descending (newest first)
        filteredEvents.sort((a, b) => new Date(b.time || b.created_at) - new Date(a.time || a.created_at));
        
        timelineList.innerHTML = filteredEvents.map(event => this.createTimelineEvent(event)).join('');
    }
    
    /**
     * Filter timeline events based on current filter settings
     */
    filterTimelineEvents() {
        const { type, player } = this.filters.timeline;
        let events = [...this.cache.encounters];
        
        // Add artificial event types for better UX
        events = events.map(encounter => {
            let eventType = 'encounter';
            if (encounter.status === 'caught') eventType = 'catch';
            if (encounter.status === 'fainted') eventType = 'faint';
            
            return { ...encounter, eventType };
        });
        
        // Filter by event type
        if (type !== 'all') {
            events = events.filter(event => event.eventType === type);
        }
        
        // Filter by player
        if (player !== 'all') {
            events = events.filter(event => event.player_id === player);
        }
        
        return events;
    }
    
    /**
     * Create HTML for a timeline event
     */
    createTimelineEvent(event) {
        const eventType = event.eventType || 'encounter';
        const player = this.cache.players.find(p => p.id === event.player_id);
        const playerName = player ? player.name : 'Unknown Player';
        
        const icons = {
            encounter: '👁️',
            catch: '⚾',
            faint: '💀'
        };
        
        const timeAgo = this.getTimeAgo(event.time || event.created_at);
        
        return `
            <div class="timeline-event ${eventType}">
                <div class="timeline-icon ${eventType}">
                    ${icons[eventType]}
                </div>
                <div class="timeline-details">
                    <div class="timeline-header">
                        <div class="timeline-title">${event.species_name || 'Unknown Pokemon'}</div>
                        <div class="timeline-time">${timeAgo}</div>
                    </div>
                    <div class="timeline-description">
                        ${this.getEventDescription(event, playerName)}
                    </div>
                    <div class="timeline-meta">
                        <span class="timeline-tag">Route ${event.route_id}</span>
                        <span class="timeline-tag">Level ${event.level}</span>
                        ${event.shiny ? '<span class="timeline-tag">✨ Shiny</span>' : ''}
                        ${event.encounter_method ? `<span class="timeline-tag">${event.encounter_method}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * Get descriptive text for an event
     */
    getEventDescription(event, playerName) {
        const speciesName = event.species_name || 'Unknown Pokemon';
        const eventType = event.eventType || 'encounter';
        
        switch (eventType) {
            case 'encounter':
                return `${playerName} encountered ${speciesName} on Route ${event.route_id}`;
            case 'catch':
                return `${playerName} caught ${speciesName}! Added to the team.`;
            case 'faint':
                return `${playerName}'s ${speciesName} fainted in battle. RIP.`;
            default:
                return `${playerName} had an event with ${speciesName}`;
        }
    }
    
    /**
     * Update blocklist UI with filtered families
     */
    updateBlocklistUI() {
        const blocklistGrid = document.getElementById('blocklistGrid');
        const blocklistEmpty = document.getElementById('blocklistEmpty');
        
        if (!blocklistGrid) return;
        
        // Filter blocklist based on current filters
        const filteredFamilies = this.filterBlocklistFamilies();
        
        if (filteredFamilies.length === 0) {
            blocklistGrid.style.display = 'none';
            blocklistEmpty.style.display = 'block';
            return;
        }
        
        blocklistGrid.style.display = 'grid';
        blocklistEmpty.style.display = 'none';
        
        blocklistGrid.innerHTML = filteredFamilies.map(family => this.createBlocklistFamily(family)).join('');
    }
    
    /**
     * Filter blocklist families based on current filter settings
     */
    filterBlocklistFamilies() {
        const { reason } = this.filters.blocklist;
        let families = [...this.cache.blocklist];
        
        if (reason !== 'all') {
            families = families.filter(family => family.origin === reason);
        }
        
        return families;
    }
    
    /**
     * Create HTML for a blocklist family
     */
    createBlocklistFamily(family) {
        const reasonClass = family.origin === 'caught' ? 'caught' : 'encounter';
        const reasonText = family.origin === 'caught' ? 'Caught' : 'Encountered';
        const timeAgo = this.getTimeAgo(family.created_at);
        
        return `
            <div class="blocklist-family ${reasonClass}">
                <div class="blocklist-header">
                    <div class="family-name">${family.family_name || 'Unknown Family'}</div>
                    <div class="block-reason ${reasonClass}">${reasonText}</div>
                </div>
                <div class="species-list">
                    ${(family.species || []).map(species => 
                        `<span class="species-badge">${species}</span>`
                    ).join('')}
                </div>
                <div class="block-details">
                    Blocked ${timeAgo} • Evolution family no longer available for any player
                </div>
            </div>
        `;
    }
    
    /**
     * Get human-readable time difference
     */
    getTimeAgo(timestamp) {
        if (!timestamp) return 'Unknown time';
        
        const now = new Date();
        const time = new Date(timestamp);
        const diffMs = now - time;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return time.toLocaleDateString();
    }
    
    /**
     * Update player filter dropdown with current players
     */
    updatePlayerFilter() {
        const playerFilter = document.getElementById('playerFilter');
        if (!playerFilter) return;
        
        const currentValue = playerFilter.value;
        playerFilter.innerHTML = '<option value="all">All Players</option>';
        
        this.cache.players.forEach(player => {
            const option = document.createElement('option');
            option.value = player.id;
            option.textContent = player.name;
            if (player.id === currentValue) option.selected = true;
            playerFilter.appendChild(option);
        });
    }
}

// Global functions for HTML onclick handlers (define immediately)
window.showRunSelector = function() {
    if (window.soulLinkDashboard) {
        window.soulLinkDashboard.showRunSelector();
    } else {
        // Fallback: create a simple run selector modal
        console.log('Dashboard not ready, opening admin panel');
        window.open('/admin', '_blank');
    }
};

window.hideRunSelector = function() {
    if (window.soulLinkDashboard) {
        window.soulLinkDashboard.hideRunSelector();
    }
};

// Authentication setup functions
window.showTokenSetup = function() {
    // Redirect to player setup page for login
    window.location.href = '/player.html';
};

window.hideTokenSetup = function() {
    // Legacy function - no longer needed with new auth system
};

window.saveToken = function() {
    // Legacy function - no longer needed with new auth system
    Utils.showError('Please use the player setup page to login');
};

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.soulLinkDashboard = new SoulLinkDashboard();
});

window.addEventListener('beforeunload', () => {
    if (window.soulLinkDashboard) {
        window.soulLinkDashboard.destroy();
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SoulLinkDashboard;
}