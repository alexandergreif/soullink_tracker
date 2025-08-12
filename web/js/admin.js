/**
 * SoulLink Tracker Admin UI - Admin Setup and Management
 * Handles run creation, player management, and token generation
 */

class AdminUI {
    constructor({ apiUrl }) {
        this.apiUrl = apiUrl;
        this.elements = {};
        this.currentRunId = null;
        
        this.init();
    }
    
    /**
     * Initialize admin UI
     */
    init() {
        this.bindElements();
        this.bindEvents();
    }
    
    /**
     * Bind DOM elements
     */
    bindElements() {
        this.elements = {
            setupSection: document.getElementById('setupSection'),
            
            // Create Run elements
            createRunForm: document.getElementById('createRunForm'),
            runNameInput: document.getElementById('runNameInput'),
            createRunBtn: document.getElementById('createRunBtn'),
            
            // Select Run elements
            runSelect: document.getElementById('runSelect'),
            openDashboardBtn: document.getElementById('openDashboardBtn'),
            
            // Add Player elements
            addPlayerForm: document.getElementById('addPlayerForm'),
            playerNameInput: document.getElementById('playerNameInput'),
            playerGameSelect: document.getElementById('playerGameSelect'),
            playerRegionInput: document.getElementById('playerRegionInput'),
            addPlayerBtn: document.getElementById('addPlayerBtn'),
            
            // Token display
            tokensList: document.getElementById('tokensList'),
            tokenModal: document.getElementById('tokenModal'),
            tokenModalBody: document.getElementById('tokenModalBody'),
            tokenModalClose: document.getElementById('tokenModalClose'),
            
            // Navigation
            setupToggleBtn: document.getElementById('setupToggleBtn'),
            dashboardSections: document.querySelectorAll('.main .section:not(#setupSection)'),
        };
    }
    
    /**
     * Bind event listeners
     */
    bindEvents() {
        // Create run form
        if (this.elements.createRunForm) {
            this.elements.createRunForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleCreateRun();
            });
        }
        
        // Run selection
        if (this.elements.runSelect) {
            this.elements.runSelect.addEventListener('change', (e) => {
                const runId = e.target.value;
                if (runId && Utils.isValidUUID(runId)) {
                    this.selectRun(runId);
                }
            });
        }
        
        // Open dashboard button
        if (this.elements.openDashboardBtn) {
            this.elements.openDashboardBtn.addEventListener('click', () => {
                const runId = this.elements.runSelect?.value;
                if (runId && Utils.isValidUUID(runId)) {
                    this.selectRun(runId);
                    this.hideSetup();
                }
            });
        }
        
        // Add player form
        if (this.elements.addPlayerForm) {
            this.elements.addPlayerForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleAddPlayer();
            });
        }
        
        // Setup toggle
        if (this.elements.setupToggleBtn) {
            this.elements.setupToggleBtn.addEventListener('click', () => {
                this.toggleSetupView();
            });
        }
        
        // Token modal close
        if (this.elements.tokenModalClose) {
            this.elements.tokenModalClose.addEventListener('click', () => {
                this.hideTokenModal();
            });
        }
        
        // Token modal backdrop click
        if (this.elements.tokenModal) {
            this.elements.tokenModal.addEventListener('click', (e) => {
                if (e.target === this.elements.tokenModal) {
                    this.hideTokenModal();
                }
            });
        }
    }
    
    /**
     * Show setup wizard
     */
    async showSetup() {
        try {
            // Show setup section, hide dashboard sections
            if (this.elements.setupSection) {
                this.elements.setupSection.style.display = 'block';
            }
            
            this.elements.dashboardSections.forEach(section => {
                section.style.display = 'none';
            });
            
            // Load existing runs
            await this.refreshRuns();
            
            console.log('Admin setup wizard displayed');
        } catch (error) {
            console.error('Error showing setup:', error);
            Utils.showError('Failed to show setup wizard');
        }
    }
    
    /**
     * Hide setup wizard and show dashboard
     */
    hideSetup() {
        if (this.elements.setupSection) {
            this.elements.setupSection.style.display = 'none';
        }
        
        this.elements.dashboardSections.forEach(section => {
            section.style.display = 'block';
        });
    }
    
    /**
     * Toggle between setup and dashboard view
     */
    toggleSetupView() {
        const isSetupVisible = this.elements.setupSection?.style.display !== 'none';
        
        if (isSetupVisible) {
            this.hideSetup();
        } else {
            this.showSetup();
        }
    }
    
    /**
     * Refresh runs dropdown
     */
    async refreshRuns() {
        try {
            const response = await fetch(`${this.apiUrl}/v1/runs`);
            
            if (!response.ok) {
                throw new Error(`Failed to fetch runs: ${response.status}`);
            }
            
            const data = await response.json();
            const runs = Array.isArray(data) ? data : (data.runs || []);
            
            this.populateRunsDropdown(runs);
            
        } catch (error) {
            console.error('Error fetching runs:', error);
            Utils.showError('Failed to load runs');
        }
    }
    
    /**
     * Populate runs dropdown
     */
    populateRunsDropdown(runs) {
        if (!this.elements.runSelect) return;
        
        // Clear existing options
        this.elements.runSelect.innerHTML = '<option value="">Select a run...</option>';
        
        runs.forEach(run => {
            const option = document.createElement('option');
            option.value = run.id;
            option.textContent = run.name;
            this.elements.runSelect.appendChild(option);
        });
        
        // Auto-select if only one run exists
        if (runs.length === 1) {
            this.elements.runSelect.value = runs[0].id;
            this.currentRunId = runs[0].id;
            
            // Enable add player form
            this.enablePlayerForm();
        }
    }
    
    /**
     * Handle create run form submission
     */
    async handleCreateRun() {
        const runName = this.elements.runNameInput?.value?.trim();
        
        if (!runName) {
            Utils.showError('Run name is required');
            return;
        }
        
        try {
            this.setLoading(this.elements.createRunBtn, true);
            
            const response = await fetch(`${this.apiUrl}/v1/admin/runs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: runName,
                    rules_json: {},
                }),
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Failed to create run: ${response.status}`);
            }
            
            const run = await response.json();
            
            // Clear form
            this.elements.runNameInput.value = '';
            
            // Refresh runs and select the new one
            await this.refreshRuns();
            this.elements.runSelect.value = run.id;
            this.selectRun(run.id);
            
            Utils.showSuccess(`Run "${run.name}" created successfully!`);
            
        } catch (error) {
            console.error('Error creating run:', error);
            Utils.showError(error.message);
        } finally {
            this.setLoading(this.elements.createRunBtn, false);
        }
    }
    
    /**
     * Select a run and set it as current
     */
    selectRun(runId) {
        if (!runId || !Utils.isValidUUID(runId)) {
            console.warn('Invalid run ID:', runId);
            return;
        }
        
        this.currentRunId = runId;
        
        // Store in localStorage
        Utils.storage.set('currentRunId', runId);
        
        // Update URL
        const url = new URL(window.location.href);
        url.searchParams.set('run', runId);
        window.history.replaceState({}, '', url.toString());
        
        // Enable player form
        this.enablePlayerForm();
        
        // Dispatch event for dashboard to pick up
        window.dispatchEvent(new CustomEvent('soullink:run_selected', {
            detail: { runId }
        }));
        
        console.log('Run selected:', runId);
    }
    
    /**
     * Enable player form when run is selected
     */
    enablePlayerForm() {
        if (this.elements.addPlayerForm) {
            this.elements.addPlayerForm.style.opacity = '1';
            this.elements.addPlayerForm.style.pointerEvents = 'auto';
            
            // Enable form inputs
            [this.elements.playerNameInput, this.elements.playerGameSelect, 
             this.elements.playerRegionInput, this.elements.addPlayerBtn].forEach(el => {
                if (el) el.disabled = false;
            });
        }
    }
    
    /**
     * Handle add player form submission
     */
    async handleAddPlayer() {
        if (!this.currentRunId) {
            Utils.showError('Please select a run first');
            return;
        }
        
        const playerName = this.elements.playerNameInput?.value?.trim();
        const playerGame = this.elements.playerGameSelect?.value || 'Unknown';
        const playerRegion = this.elements.playerRegionInput?.value?.trim() || 'Unknown';
        
        if (!playerName) {
            Utils.showError('Player name is required');
            return;
        }
        
        try {
            this.setLoading(this.elements.addPlayerBtn, true);
            
            const response = await fetch(`${this.apiUrl}/v1/admin/runs/${this.currentRunId}/players`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: playerName,
                    game: playerGame,
                    region: playerRegion,
                }),
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Failed to create player: ${response.status}`);
            }
            
            const player = await response.json();
            
            // Clear form
            this.elements.playerNameInput.value = '';
            this.elements.playerRegionInput.value = '';
            
            // Show token modal
            this.showTokenModal(player);
            
            // Add to tokens list
            this.addToTokensList(player);
            
            Utils.showSuccess(`Player "${player.name}" created successfully!`);
            
        } catch (error) {
            console.error('Error creating player:', error);
            Utils.showError(error.message);
        } finally {
            this.setLoading(this.elements.addPlayerBtn, false);
        }
    }
    
    /**
     * Show token modal with copy functionality
     */
    showTokenModal(player) {
        if (!this.elements.tokenModal || !this.elements.tokenModalBody) return;
        
        const modalContent = `
            <div class="token-display">
                <h4>Player Token for "${player.name}"</h4>
                <p class="token-warning">⚠️ <strong>IMPORTANT:</strong> This token will only be shown once! Copy it now.</p>
                <div class="token-container">
                    <input type="text" class="token-input" value="${player.new_token}" readonly>
                    <button class="copy-btn" onclick="this.parentElement.querySelector('.token-input').select(); document.execCommand('copy'); this.textContent='Copied!'">Copy</button>
                </div>
                <div class="player-details">
                    <p><strong>Player:</strong> ${player.name}</p>
                    <p><strong>Game:</strong> ${player.game}</p>
                    <p><strong>Region:</strong> ${player.region}</p>
                    <p><strong>Created:</strong> ${new Date(player.created_at).toLocaleString()}</p>
                </div>
            </div>
        `;
        
        this.elements.tokenModalBody.innerHTML = modalContent;
        this.elements.tokenModal.classList.add('show');
        
        // Auto-select token for easy copying
        setTimeout(() => {
            const tokenInput = this.elements.tokenModalBody.querySelector('.token-input');
            if (tokenInput) {
                tokenInput.select();
            }
        }, 100);
    }
    
    /**
     * Hide token modal
     */
    hideTokenModal() {
        if (this.elements.tokenModal) {
            this.elements.tokenModal.classList.remove('show');
        }
    }
    
    /**
     * Add player to tokens list
     */
    addToTokensList(player) {
        if (!this.elements.tokensList) return;
        
        const tokenItem = document.createElement('div');
        tokenItem.className = 'token-item';
        tokenItem.innerHTML = `
            <div class="token-info">
                <div class="token-player">${player.name}</div>
                <div class="token-details">${player.game} | ${player.region}</div>
                <div class="token-created">${new Date(player.created_at).toLocaleString()}</div>
            </div>
            <div class="token-actions">
                <span class="token-status">Token generated ✓</span>
            </div>
        `;
        
        this.elements.tokensList.appendChild(tokenItem);
    }
    
    /**
     * Set loading state for buttons
     */
    setLoading(button, loading) {
        if (!button) return;
        
        if (loading) {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = 'Loading...';
        } else {
            button.disabled = false;
            button.textContent = button.dataset.originalText || button.textContent;
        }
    }
}

// Auto-initialize if not already done
document.addEventListener('DOMContentLoaded', () => {
    // AdminUI will be created by dashboard.js when needed
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdminUI;
}