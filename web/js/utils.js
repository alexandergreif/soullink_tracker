/**
 * SoulLink Tracker Dashboard - Utility Functions
 * Common utility functions for the dashboard
 */

class Utils {
    /**
     * Format a timestamp for display
     * @param {string|Date} timestamp - ISO timestamp or Date object
     * @returns {string} Formatted time string
     */
    static formatTime(timestamp) {
        const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
        const now = new Date();
        const diff = now - date;
        
        // Less than 1 minute ago
        if (diff < 60000) {
            return 'Just now';
        }
        
        // Less than 1 hour ago
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `${minutes}m ago`;
        }
        
        // Less than 1 day ago
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours}h ago`;
        }
        
        // More than 1 day ago - show date
        return date.toLocaleDateString();
    }
    
    /**
     * Format a relative time (e.g., "5 minutes ago")
     * @param {string|Date} timestamp - ISO timestamp or Date object
     * @returns {string} Relative time string
     */
    static formatRelativeTime(timestamp) {
        const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
        const now = new Date();
        const diff = now - date;
        
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (seconds < 30) return 'Just now';
        if (seconds < 60) return `${seconds} seconds ago`;
        if (minutes < 60) return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
        if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
        return `${days} day${days !== 1 ? 's' : ''} ago`;
    }
    
    /**
     * Capitalize first letter of a string
     * @param {string} str - String to capitalize
     * @returns {string} Capitalized string
     */ 
    static capitalize(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
    }
    
    /**
     * Convert snake_case to Title Case
     * @param {string} str - Snake case string
     * @returns {string} Title case string
     */
    static snakeToTitle(str) {
        if (!str) return '';
        return str
            .split('_')
            .map(word => this.capitalize(word))
            .join(' ');
    }
    
    /**
     * Get Pokemon species name from ID (basic mapping)
     * @param {number} speciesId - Pokemon species ID
     * @returns {string} Pokemon name
     */
    static getPokemonName(speciesId) {
        // Basic mapping - in a real app this would come from API
        const basicNames = {
            1: 'Bulbasaur', 4: 'Charmander', 7: 'Squirtle', 25: 'Pikachu',
            152: 'Chikorita', 155: 'Cyndaquil', 158: 'Totodile'
        };
        return basicNames[speciesId] || `Pokemon #${speciesId}`;
    }
    
    /**
     * Get route name from ID
     * @param {number} routeId - Route ID
     * @returns {string} Route name
     */
    static getRouteName(routeId) {
        if (routeId >= 1 && routeId <= 20) {
            return `Route ${28 + routeId}`;
        }
        if (routeId >= 21 && routeId <= 47) {
            return `Route ${routeId - 20}`;
        }
        
        const specialRoutes = {
            100: 'New Bark Town',
            101: 'Cherrygrove City', 
            102: 'Violet City',
            103: 'Azalea Town',
            104: 'Goldenrod City',
            200: 'Pallet Town',
            201: 'Viridian City'
        };
        
        return specialRoutes[routeId] || `Location #${routeId}`;
    }
    
    /**
     * Get encounter method icon
     * @param {string} method - Encounter method
     * @returns {string} Icon/emoji for the method
     */
    static getEncounterIcon(method) {
        const icons = {
            'grass': '🌱',
            'water': '🌊', 
            'fishing': '🎣',
            'surfing': '🏄',
            'headbutt': '🌳',
            'rock_smash': '🪨',
            'gift': '🎁',
            'trade': '🔄'
        };
        return icons[method] || '❓';
    }
    
    /**
     * Get event type icon  
     * @param {string} eventType - Event type
     * @returns {string} Icon/emoji for the event
     */
    static getEventIcon(eventType) {
        const icons = {
            'encounter': '👁️',
            'caught': '⚾',
            'fled': '💨',
            'faint': '💀',
            'soul_link': '🔗',
            'admin': '⚙️'
        };
        return icons[eventType] || '📝';
    }
    
    /**
     * Generate a random ID
     * @returns {string} Random ID string
     */
    static generateId() {
        return Math.random().toString(36).substr(2, 9);
    }
    
    /**
     * Debounce function calls
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Throttle function calls
     * @param {Function} func - Function to throttle
     * @param {number} limit - Time limit in milliseconds
     * @returns {Function} Throttled function
     */
    static throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
    
    /**
     * Create a DOM element with attributes and content
     * @param {string} tag - HTML tag name
     * @param {Object} attributes - Element attributes
     * @param {string|Node|Node[]} content - Element content
     * @returns {HTMLElement} Created element
     */
    static createElement(tag, attributes = {}, content = '') {
        const element = document.createElement(tag);
        
        // Set attributes
        Object.entries(attributes).forEach(([key, value]) => {
            if (key === 'className') {
                element.className = value;
            } else if (key === 'data') {
                Object.entries(value).forEach(([dataKey, dataValue]) => {
                    element.dataset[dataKey] = dataValue;
                });
            } else {
                element.setAttribute(key, value);
            }
        });
        
        // Set content
        if (typeof content === 'string') {
            element.innerHTML = content;
        } else if (content instanceof Node) {
            element.appendChild(content);
        } else if (Array.isArray(content)) {
            content.forEach(child => {
                if (child instanceof Node) {
                    element.appendChild(child);
                }
            });
        }
        
        return element;
    }
    
    /**
     * Show toast notification
     * @param {string} message - Message to show
     * @param {string} type - Toast type ('success', 'error', 'info')
     * @param {number} duration - Duration in milliseconds
     */
    static showToast(message, type = 'info', duration = 5000) {
        const toastId = type === 'error' ? 'errorToast' : 'successToast';
        const messageId = type === 'error' ? 'errorMessage' : 'successMessage';
        
        const toast = document.getElementById(toastId);
        const messageEl = document.getElementById(messageId);
        
        if (!toast || !messageEl) return;
        
        messageEl.textContent = message;
        toast.classList.add('show');
        
        // Auto-hide after duration
        setTimeout(() => {
            toast.classList.remove('show');
        }, duration);
    }
    
    /**
     * Show error toast
     * @param {string} message - Error message
     */
    static showError(message) {
        this.showToast(message, 'error');
    }
    
    /**
     * Show success toast
     * @param {string} message - Success message
     */
    static showSuccess(message) {
        this.showToast(message, 'success');
    }
    
    /**
     * Format large numbers with commas
     * @param {number} num - Number to format
     * @returns {string} Formatted number string
     */
    static formatNumber(num) {
        return num.toLocaleString();
    }
    
    /**
     * Safely parse JSON with error handling
     * @param {string} jsonString - JSON string to parse
     * @param {*} defaultValue - Default value if parsing fails
     * @returns {*} Parsed object or default value
     */
    static safeJsonParse(jsonString, defaultValue = null) {
        try {
            return JSON.parse(jsonString);
        } catch (e) {
            console.error('JSON parse error:', e);
            return defaultValue;
        }
    }
    
    /**
     * Copy text to clipboard
     * @param {string} text - Text to copy
     * @returns {Promise<boolean>} Success status
     */
    static async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            return true;
        }
    }
    
    /**
     * Validate if a string is a valid UUID
     * @param {string} uuid - UUID string to validate
     * @returns {boolean} Whether the UUID is valid
     */
    static isValidUUID(uuid) {
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        return uuidRegex.test(uuid);
    }
    
    /**
     * Make authenticated API request
     * @param {string} url - API endpoint URL
     * @param {Object} options - Fetch options
     * @returns {Promise<Response>} Fetch response
     */
    static async apiRequest(url, options = {}) {
        const authHeader = Utils.auth.getAuthHeader();
        const headers = {
            'Content-Type': 'application/json',
            ...authHeader,
            ...(options.headers || {})
        };
        
        return fetch(url, {
            ...options,
            headers
        });
    }
    
    /**
     * Redirect to login page if not authenticated
     */
    static requireAuth() {
        if (!Utils.auth.isAuthenticated()) {
            const currentUrl = new URL(window.location.href);
            const apiParam = currentUrl.searchParams.get('api');
            
            let playerUrl = '/player.html';
            if (apiParam) {
                playerUrl += `?api=${encodeURIComponent(apiParam)}`;
            }
            
            window.location.href = playerUrl;
            return false;
        }
        return true;
    }
    
    /**
     * Get URL parameters
     * @returns {Object} URL parameters as key-value pairs
     */
    static getUrlParams() {
        const params = new URLSearchParams(window.location.search);
        const result = {};
        for (const [key, value] of params) {
            result[key] = value;
        }
        return result;
    }
    
    /**
     * Set page title with notification count
     * @param {number} count - Notification count
     * @param {string} baseTitle - Base page title
     */
    static setPageTitle(count = 0, baseTitle = 'SoulLink Tracker') {
        document.title = count > 0 ? `(${count}) ${baseTitle}` : baseTitle;
    }
    
    /**
     * Local storage helpers with error handling
     */
    static storage = {
        get(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch (e) {
                console.error('Storage get error:', e);
                return defaultValue;
            }
        },
        
        set(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
                return true;
            } catch (e) {
                console.error('Storage set error:', e);
                return false;
            }
        },
        
        remove(key) {
            try {
                localStorage.removeItem(key);
                return true;
            } catch (e) {
                console.error('Storage remove error:', e);
                return false;
            }
        }
    };
    
    /**
     * Authentication and session management helpers
     */
    static auth = {
        /**
         * Get current session data
         * @returns {Object} Session data with sessionToken, runId, playerId, etc.
         */
        getSessionData() {
            return {
                sessionToken: localStorage.getItem('soullink_session_token') || localStorage.getItem('sessionToken'),
                runId: localStorage.getItem('soullink_run_id'),
                playerId: localStorage.getItem('soullink_player_id'),
                runName: localStorage.getItem('soullink_run_name'),
                playerName: localStorage.getItem('soullink_player_name')
            };
        },
        
        /**
         * Check if user has a valid session
         * @returns {boolean} Whether user has valid session
         */
        isAuthenticated() {
            const session = this.getSessionData();
            return !!(session.sessionToken && session.runId && session.playerId);
        },
        
        /**
         * Get authentication header for API requests
         * @returns {Object|null} Authorization header object or null
         */
        getAuthHeader() {
            const session = this.getSessionData();
            if (session.sessionToken) {
                return { 'Authorization': `Bearer ${session.sessionToken}` };
            }
            return null;
        },
        
        /**
         * Clear all session data
         */
        clearSession() {
            const keys = [
                'soullink_session_token',
                'sessionToken',
                'soullink_run_id',
                'soullink_player_id',
                'soullink_run_name',
                'soullink_player_name',
                'soullink_player_token' // Legacy
            ];
            
            keys.forEach(key => {
                try {
                    localStorage.removeItem(key);
                } catch (e) {
                    console.warn(`Failed to remove ${key}:`, e);
                }
            });
        }
    };
    
    /**
     * Legacy token helpers (for backward compatibility)
     */
    static token = {
        /**
         * Validate if a token has the correct format
         * @param {string} token - Token to validate
         * @returns {boolean} True if token appears valid
         */
        isValid(token) {
            return token && 
                   typeof token === 'string' && 
                   token.length >= 20 && 
                   !token.includes(' ') && 
                   !token.includes('\n') &&
                   token.trim() === token;
        },
        
        /**
         * Get bearer token (now uses session system)
         * @returns {string|null} Valid token or null
         */
        getBearerToken() {
            const session = Utils.auth.getSessionData();
            return session.sessionToken;
        },
        
        /**
         * Set bearer token (legacy compatibility)
         * @param {string} token - Token to store
         * @param {string} key - Storage key (optional)
         */
        setBearerToken(token, key = 'soullink_session_token') {
            if (!this.isValid(token)) {
                console.error('Invalid token format provided');
                return false;
            }
            
            try {
                localStorage.setItem(key, token.trim());
                return true;
            } catch (e) {
                console.error('Failed to save token:', e);
                return false;
            }
        },
        
        /**
         * Clear all stored tokens (now uses auth.clearSession)
         */
        clearAll() {
            Utils.auth.clearSession();
        }
    };
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Utils;
}