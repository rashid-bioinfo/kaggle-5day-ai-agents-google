// Application State
let appState = {
    releases: [],
    filteredReleases: [],
    currentFilter: 'all',
    searchQuery: '',
    isLoading: false,
    selectedRelease: null
};

// DOM Elements
const elements = {
    refreshBtn: document.getElementById('refresh-btn'),
    exportCsvBtn: document.getElementById('export-csv-btn'),
    lastUpdatedTime: document.getElementById('last-updated-time'),
    searchInput: document.getElementById('search-input'),
    clearSearchBtn: document.getElementById('clear-search'),
    filterTagsContainer: document.getElementById('filter-tags-container'),
    resultsCount: document.getElementById('results-count'),
    activeFiltersDesc: document.getElementById('active-filters-desc'),
    releaseListContainer: document.getElementById('release-list-container'),
    toast: document.getElementById('toast'),
    
    // Tweet Modal Elements
    tweetModal: document.getElementById('tweet-modal'),
    tweetTextArea: document.getElementById('tweet-text-area'),
    charCounter: document.getElementById('char-counter'),
    closeModalBtn: document.getElementById('close-modal-btn'),
    cancelTweetBtn: document.getElementById('cancel-tweet-btn'),
    shareTweetBtn: document.getElementById('share-tweet-btn')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    fetchReleases(false); // Initial load (uses cache)
});

// Event Listeners Setup
function setupEventListeners() {
    // Refresh button
    elements.refreshBtn.addEventListener('click', () => {
        fetchReleases(true); // Force fresh crawl
    });
    
    // Export CSV button
    elements.exportCsvBtn.addEventListener('click', () => {
        exportToCSV();
    });
    
    // Search input
    elements.searchInput.addEventListener('input', (e) => {
        appState.searchQuery = e.target.value;
        toggleClearSearchButton();
        applyFilters();
    });
    
    // Clear search button
    elements.clearSearchBtn.addEventListener('click', () => {
        elements.searchInput.value = '';
        appState.searchQuery = '';
        toggleClearSearchButton();
        applyFilters();
        elements.searchInput.focus();
    });
    
    // Filter tags
    elements.filterTagsContainer.addEventListener('click', (e) => {
        const filterTag = e.target.closest('.filter-tag');
        if (!filterTag) return;
        
        // Update active tag styling
        document.querySelectorAll('.filter-tag').forEach(tag => tag.classList.remove('active'));
        filterTag.classList.add('active');
        
        // Update state and apply filter
        appState.currentFilter = filterTag.dataset.filter;
        applyFilters();
    });
    
    // Tweet modal close events
    elements.closeModalBtn.addEventListener('click', closeTweetModal);
    elements.cancelTweetBtn.addEventListener('click', closeTweetModal);
    elements.tweetModal.addEventListener('click', (e) => {
        if (e.target === elements.tweetModal) closeTweetModal();
    });
    
    // Escape key to close modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !elements.tweetModal.classList.contains('hidden')) {
            closeTweetModal();
        }
    });
    
    // Tweet textarea character count listener
    elements.tweetTextArea.addEventListener('input', updateTweetCharCounter);
    
    // Share tweet button click
    elements.shareTweetBtn.addEventListener('click', (e) => {
        const tweetText = elements.tweetTextArea.value.trim();
        if (tweetText.length === 0) {
            e.preventDefault();
            showToast('Tweet content cannot be empty.');
            return;
        }
        if (tweetText.length > 280) {
            e.preventDefault();
            showToast('Tweet exceeds character limit.');
            return;
        }
        
        // Dynamically update tweet intent href
        elements.shareTweetBtn.href = `https://twitter.com/intent/tweet?text=${encodeURIComponent(tweetText)}`;
        
        // Close modal after brief delay
        setTimeout(closeTweetModal, 500);
    });
}

// Fetch Release Notes from API
async function fetchReleases(forceRefresh = false) {
    if (appState.isLoading) return;
    
    setLoadingState(true);
    
    try {
        const url = `/api/releases${forceRefresh ? '?refresh=true' : ''}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
            appState.releases = result.releases;
            elements.lastUpdatedTime.textContent = `Last Checked: ${result.last_fetched}`;
            showToast(forceRefresh ? 'Release notes refreshed!' : 'Loaded successfully.');
        } else {
            throw new Error(result.message || 'Unknown server error');
        }
        
    } catch (error) {
        console.error('Error fetching release notes:', error);
        showToast('Failed to fetch release notes. Try again.');
        
        // If we don't have releases in state, show an error state in list container
        if (appState.releases.length === 0) {
            renderErrorState(error.message);
        }
    } finally {
        setLoadingState(false);
        applyFilters();
    }
}

// Toggle loading states
function setLoadingState(isLoading) {
    appState.isLoading = isLoading;
    
    if (isLoading) {
        elements.refreshBtn.disabled = true;
        elements.refreshBtn.querySelector('.spinner-icon').classList.remove('hidden');
        elements.refreshBtn.querySelector('.refresh-arrow-icon').classList.add('hidden');
        renderSkeletons();
    } else {
        elements.refreshBtn.disabled = false;
        elements.refreshBtn.querySelector('.spinner-icon').classList.add('hidden');
        elements.refreshBtn.querySelector('.refresh-arrow-icon').classList.remove('hidden');
    }
}

// Render skeleton loaders during API call
function renderSkeletons() {
    elements.releaseListContainer.innerHTML = `
        <div class="skeleton-card glass-panel">
            <div class="skeleton-header">
                <div class="skeleton-badge"></div>
                <div class="skeleton-date"></div>
            </div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line short"></div>
            <div class="skeleton-footer"></div>
        </div>
        <div class="skeleton-card glass-panel">
            <div class="skeleton-header">
                <div class="skeleton-badge"></div>
                <div class="skeleton-date"></div>
            </div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line short"></div>
            <div class="skeleton-footer"></div>
        </div>
        <div class="skeleton-card glass-panel">
            <div class="skeleton-header">
                <div class="skeleton-badge"></div>
                <div class="skeleton-date"></div>
            </div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line short"></div>
            <div class="skeleton-footer"></div>
        </div>
    `;
}

// Render error state inside container
function renderErrorState(message) {
    elements.releaseListContainer.innerHTML = `
        <div class="empty-state glass-panel">
            <div class="empty-icon">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
            </div>
            <h3>Unable to retrieve release notes</h3>
            <p>${message || 'There was a connection issue with the server feed parser.'}</p>
            <button onclick="window.location.reload()" class="btn btn-secondary">Retry App Load</button>
        </div>
    `;
}

// Show/Hide search clear button
function toggleClearSearchButton() {
    if (appState.searchQuery.trim().length > 0) {
        elements.clearSearchBtn.classList.remove('hidden');
    } else {
        elements.clearSearchBtn.classList.add('hidden');
    }
}

// Client-side filtering & searching logic
function applyFilters() {
    const filter = appState.currentFilter.toLowerCase();
    const query = appState.searchQuery.toLowerCase().trim();
    
    appState.filteredReleases = appState.releases.filter(item => {
        // Apply type filter
        const matchesType = (filter === 'all' || item.type.toLowerCase() === filter);
        
        // Apply search query filter
        const matchesQuery = !query || 
            item.date.toLowerCase().includes(query) ||
            item.type.toLowerCase().includes(query) ||
            item.content_text.toLowerCase().includes(query);
            
        return matchesType && matchesQuery;
    });
    
    // Update Stats Bar
    elements.resultsCount.textContent = `Showing ${appState.filteredReleases.length} of ${appState.releases.length} updates`;
    
    let activeFilters = [];
    if (filter !== 'all') activeFilters.push(`Type: ${appState.currentFilter}`);
    if (query) activeFilters.push(`Search: "${appState.searchQuery}"`);
    elements.activeFiltersDesc.textContent = activeFilters.length > 0 ? `Active filters (${activeFilters.join(', ')})` : '';
    
    renderReleaseNotes();
}

// Render release notes to page
function renderReleaseNotes() {
    const container = elements.releaseListContainer;
    container.innerHTML = '';
    
    if (appState.filteredReleases.length === 0) {
        container.innerHTML = `
            <div class="empty-state glass-panel">
                <div class="empty-icon">
                    <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="11" cy="11" r="8"></circle>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                </div>
                <h3>No release notes match your query</h3>
                <p>Try clearing your search keyword or selecting a different update type filter.</p>
            </div>
        `;
        return;
    }
    
    appState.filteredReleases.forEach(item => {
        // Map type class
        const typeClass = item.type.toLowerCase();
        
        // Create Release Card
        const card = document.createElement('article');
        card.className = `release-card glass-panel ${typeClass}`;
        
        card.innerHTML = `
            <header class="card-header">
                <div class="badge-and-date">
                    <span class="type-badge ${typeClass}">${escapeHtml(item.type)}</span>
                    <span class="release-date">${escapeHtml(item.date)}</span>
                </div>
            </header>
            
            <div class="card-content">
                ${item.content_html}
            </div>
            
            <footer class="card-footer">
                <div class="action-buttons">
                    <button class="btn btn-twitter-share" data-id="${item.id}" title="Compose tweet for this update">
                        <span class="twitter-icon">
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                            </svg>
                        </span>
                        <span>Tweet Update</span>
                    </button>
                    
                    <button class="btn-text-copy btn-copy-text" data-id="${item.id}" title="Copy release note text and link to clipboard">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                        <span>Copy to Clipboard</span>
                    </button>
                    
                    <button class="btn-text-copy btn-copy-link" data-id="${item.id}" title="Copy link to this release note section">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                        </svg>
                        <span>Copy Link</span>
                    </button>
                </div>
                
                <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="original-link" title="Open Google Cloud documentation">
                    <span>Source Notes</span>
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="7" y1="17" x2="17" y2="7"></line>
                        <polyline points="7 7 17 7 17 17"></polyline>
                    </svg>
                </a>
            </footer>
        `;
        
        // Attach Button Listeners
        card.querySelector('.btn-twitter-share').addEventListener('click', () => {
            openTweetComposer(item);
        });
        
        card.querySelector('.btn-copy-text').addEventListener('click', () => {
            copyTextToClipboard(item);
        });
        
        card.querySelector('.btn-copy-link').addEventListener('click', () => {
            copyLinkToClipboard(item);
        });
        
        container.appendChild(card);
    });
}

// Clipboard Functions
function copyTextToClipboard(item) {
    const textToCopy = `BigQuery Release Note (${item.date}) [${item.type}]: ${item.content_text}\nSource: ${item.url}`;
    navigator.clipboard.writeText(textToCopy)
        .then(() => showToast('Plain text summary copied to clipboard!'))
        .catch(err => {
            console.error('Could not copy text: ', err);
            showToast('Failed to copy text. Please copy manually.');
        });
}

function copyLinkToClipboard(item) {
    navigator.clipboard.writeText(item.url)
        .then(() => showToast('Direct notes link copied to clipboard!'))
        .catch(err => {
            console.error('Could not copy link: ', err);
            showToast('Failed to copy link.');
        });
}

// Toast Notification System
let toastTimeout;
function showToast(message) {
    clearTimeout(toastTimeout);
    elements.toast.textContent = message;
    elements.toast.classList.remove('hidden');
    
    toastTimeout = setTimeout(() => {
        elements.toast.classList.add('hidden');
    }, 2500);
}

// HTML Escaping Utility
function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Twitter Composer Modal Flow
function openTweetComposer(item) {
    appState.selectedRelease = item;
    
    // Construct default Tweet draft
    // Max characters: 280
    // Twitter URLs count as 23 characters.
    // Template: BigQuery Update ({date}) [{type}]: {content} {url} #BigQuery #GoogleCloud
    const header = `BigQuery Update (${item.date}) [${item.type}]: `;
    const footer = ` #BigQuery #GoogleCloud`;
    
    // Calculate character budget
    // header length + 23 (Twitter URL length) + footer length
    const metadataLength = header.length + 23 + footer.length;
    const maxContentLength = 280 - metadataLength;
    
    let content = item.content_text.replace(/\s+/g, ' ').trim();
    if (content.length > maxContentLength) {
        // Truncate to fit budget (leaving 3 chars for ellipsis)
        content = content.substring(0, maxContentLength - 3) + '...';
    }
    
    const defaultTweet = `${header}${content} ${item.url}${footer}`;
    
    // Set textarea and show modal
    elements.tweetTextArea.value = defaultTweet;
    updateTweetCharCounter();
    elements.tweetModal.classList.remove('hidden');
    document.body.style.overflow = 'hidden'; // Disable scroll on background
    
    // Focus textarea and set cursor at end
    setTimeout(() => {
        elements.tweetTextArea.focus();
        elements.tweetTextArea.setSelectionRange(defaultTweet.length, defaultTweet.length);
    }, 100);
}

function closeTweetModal() {
    elements.tweetModal.classList.add('hidden');
    document.body.style.overflow = ''; // Re-enable scroll
    appState.selectedRelease = null;
}

// Update character count and progress styles
function updateTweetCharCounter() {
    const text = elements.tweetTextArea.value;
    
    // Real Twitter URL parsing makes counting accurate.
    // Let's count characters. For accurate counting, we replace links in the textarea with a 23 character string,
    // since Twitter handles URLs by compressing them to t.co (23 chars).
    const urlPattern = /(https?:\/\/[^\s]+)/g;
    let countedText = text;
    const urls = text.match(urlPattern);
    
    if (urls) {
        urls.forEach(url => {
            countedText = countedText.replace(url, 'x'.repeat(23));
        });
    }
    
    const count = countedText.length;
    
    elements.charCounter.textContent = `${count} / 280`;
    
    // Style classes based on length
    elements.charCounter.className = 'char-counter';
    if (count > 280) {
        elements.charCounter.classList.add('danger');
        elements.shareTweetBtn.classList.add('disabled');
        elements.shareTweetBtn.style.opacity = '0.5';
        elements.shareTweetBtn.style.pointerEvents = 'none';
    } else if (count >= 250) {
        elements.charCounter.classList.add('warning');
        elements.shareTweetBtn.classList.remove('disabled');
        elements.shareTweetBtn.style.opacity = '1';
        elements.shareTweetBtn.style.pointerEvents = 'auto';
    } else {
        elements.shareTweetBtn.classList.remove('disabled');
        elements.shareTweetBtn.style.opacity = '1';
        elements.shareTweetBtn.style.pointerEvents = 'auto';
    }
}

// Export currently filtered releases to CSV
function exportToCSV() {
    if (appState.filteredReleases.length === 0) {
        showToast('No release notes found to export.');
        return;
    }
    
    // Define CSV Headers
    const headers = ['Date', 'Type', 'Content (Plain Text)', 'Documentation URL'];
    
    // Map data rows and escape double quotes
    const rows = appState.filteredReleases.map(item => {
        const dateStr = item.date;
        const typeStr = item.type;
        // Strip linebreaks and double quotes from text content
        const cleanContent = item.content_text.replace(/\r?\n|\r/g, ' ').replace(/"/g, '""');
        const urlStr = item.url;
        
        return `"${dateStr}","${typeStr}","${cleanContent}","${urlStr}"`;
    });
    
    // Combine headers and rows
    const csvContent = [headers.join(','), ...rows].join('\n');
    
    try {
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        
        // Formulate date suffix for file name
        const dateSuffix = new Date().toISOString().slice(0, 10);
        
        link.setAttribute('href', url);
        link.setAttribute('download', `bigquery_release_notes_${dateSuffix}.csv`);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showToast('CSV export downloaded successfully!');
    } catch (err) {
        console.error('Error exporting CSV:', err);
        showToast('Export failed. Please check browser permissions.');
    }
}
