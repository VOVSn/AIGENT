// frontend/public/js/app.js

// --- GLOBAL STATE ---
// Stores information about the currently selected Aigent
let currentAigent = {
    id: null,
    name: '',
    presentationFormat: 'markdown' // Safe default
};
// Stores information about the logged-in user
let currentUser = {
    username: 'Guest',
    user_state: {},
    timezone: 'UTC'
};
let calendarRendered = false; // Flag to check if calendar has been rendered once


// --- THEME MANAGEMENT ---
const THEMES = ['light', 'dark', 'memphis'];

function applyTheme(theme) {
    if (!THEMES.includes(theme)) return;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    // For highlight.js syntax highlighting theme
    const lightThemeLink = document.getElementById('hljs-light-theme');
    const darkThemeLink = document.getElementById('hljs-dark-theme');
    if (lightThemeLink && darkThemeLink) {
        lightThemeLink.disabled = (theme === 'dark');
        darkThemeLink.disabled = (theme !== 'dark');
    }
    // Update active theme button in settings
    document.querySelectorAll('.theme-choice-btn').forEach(btn => {
        btn.classList.toggle('active-theme', btn.dataset.themeSet === theme);
    });
}
// Apply saved theme on initial load
(function() {
    applyTheme(localStorage.getItem('theme') || THEMES[0]);
})();


// --- UTILITY & API FUNCTIONS ---
function scrollToBottom(element) {
    if (element) {
        element.scrollTop = element.scrollHeight;
    }
}

async function refreshToken() {
    const currentRefreshToken = localStorage.getItem('refreshToken');
    if (!currentRefreshToken) return false;
    try {
        const response = await fetch('/api/v1/auth/token/refresh/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: currentRefreshToken })
        });
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('accessToken', data.access);
            return true;
        }
        return false;
    } catch (error) {
        return false;
    }
}

async function apiFetch(url, options = {}) {
    let accessToken = localStorage.getItem('accessToken');
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
    }

    try {
        let response = await fetch(url, { ...options, headers });
        if (response.status === 401 && !url.includes('/api/v1/auth/token/refresh/')) {
            const refreshed = await refreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${localStorage.getItem('accessToken')}`;
                response = await fetch(url, { ...options, headers });
            } else {
                logout("Session expired. Please login again.");
                return Promise.reject(new Error("Session expired. Please login again."));
            }
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({
                detail: `Request failed with status ${response.status}`
            }));
            throw new Error(errorData.detail || `API request failed: ${response.statusText} (${response.status})`);
        }
        if (response.status === 204) {
            return null; // Handle No Content response
        }
        return await response.json();
    } catch (error) {
        console.error('API Fetch General Error:', error.message);
        throw error;
    }
}

function logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('username'); // Deprecated, but good to clean up
    window.location.href = '/login.html';
}


// --- PAGE INITIALIZATION & AIGENT MANAGEMENT ---
async function setupPage() {
    // Fetch current user data and then set up the rest of the page
    try {
        const user = await apiFetch('/api/v1/auth/me/');
        currentUser = user; // Store the full user object, including user_state
        const usernameDisplayEl = document.getElementById('usernameDisplay');
        if (usernameDisplayEl) {
            usernameDisplayEl.textContent = currentUser.username;
        }

        // --- NEW: Timezone Synchronization ---
        await syncUserTimezone();

        // Once user is confirmed, proceed with page setup
        await populateAigentSelector();
        initializeTabs(); // NEW: Set up tab functionality
        loadChatHistory();

        const messageForm = document.getElementById('messageForm');
        if (messageForm) {
            messageForm.addEventListener('submit', async (event) => {
                event.preventDefault();
                const messageInput = document.getElementById('messageInput');
                const messageText = messageInput.value.trim();
                if (messageText) {
                    appendMessageToChat('user', messageText);
                    messageInput.value = '';
                    // Pass the user ID to the send message function
                    await sendMessageToAigent(messageText, currentUser.id);
                }
            });
        }
    } catch (error) {
        console.error("Failed to set up page, likely auth issue.", error);
        logout();
    }
}

// --- NEW: Timezone Synchronization Function ---
async function syncUserTimezone() {
    try {
        // Get browser's IANA timezone name
        const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        // If the browser's timezone is different from what's stored, update the backend
        if (currentUser.timezone !== browserTimezone) {
            console.log(`Timezone mismatch. Stored: ${currentUser.timezone}, Browser: ${browserTimezone}. Updating...`);
            const updatedUser = await apiFetch('/api/v1/auth/me/', {
                method: 'PATCH',
                body: JSON.stringify({ timezone: browserTimezone })
            });
            // Update the global user object with the fresh data from the server
            currentUser = updatedUser;
            console.log(`Timezone updated successfully to ${currentUser.timezone}`);
        }
    } catch (error) {
        console.error("Failed to sync user timezone:", error);
        // This is not a critical failure, so we don't need to log out.
        // The aigent will just use the last known timezone or the default 'UTC'.
    }
}

async function populateAigentSelector() {
    const selector = document.getElementById('aigent-selector');
    const aigentNameDisplay = document.getElementById('aigentNameDisplay'); // Get the new element

    if (!selector) return;

    try {
        const aigents = await apiFetch('/api/v1/aigents/list/');
        selector.innerHTML = ''; // Clear existing options

        // Find the active aigent first to set the display
        const activeAigent = aigents.find(a => a.is_active);
        if (activeAigent) {
            // Set global state for the active aigent
            currentAigent.id = activeAigent.id;
            currentAigent.name = activeAigent.name;
            currentAigent.presentationFormat = activeAigent.presentation_format;
            
            // --- NEW: Update the header display ---
            if (aigentNameDisplay) {
                aigentNameDisplay.textContent = activeAigent.name;
            }
        } else if (aigentNameDisplay) {
             aigentNameDisplay.textContent = 'N/A'; // Handle case where no aigent is active
        }

        // Now populate the selector dropdown
        aigents.forEach(aigent => {
            const option = document.createElement('option');
            option.value = aigent.id;
            option.textContent = aigent.name;
            option.dataset.presentationFormat = aigent.presentation_format;
            if (aigent.is_active) {
                option.selected = true;
            }
            selector.appendChild(option);
        });
    } catch (error) {
        console.error("Failed to populate aigents:", error);
        if (aigentNameDisplay) aigentNameDisplay.textContent = 'Error';
    }
}

async function handleAigentSwitch(event) {
    const selector = event.target;
    const newAigentId = selector.value;
    const selectedOption = selector.options[selector.selectedIndex];
    const newAigentName = selectedOption.text;
    const newPresentationFormat = selectedOption.dataset.presentationFormat;
    const aigentNameDisplay = document.getElementById('aigentNameDisplay'); // Get the new element

    try {
        await apiFetch('/api/v1/aigents/set_active/', {
            method: 'POST',
            body: JSON.stringify({ aigent_id: newAigentId })
        });
        currentAigent.id = newAigentId;
        currentAigent.name = newAigentName;
        currentAigent.presentationFormat = newPresentationFormat;

        // --- NEW: Update the header display ---
        if (aigentNameDisplay) {
            aigentNameDisplay.textContent = newAigentName;
        }

        const chatMessagesDiv = document.getElementById('chatMessages');
        if (chatMessagesDiv) chatMessagesDiv.innerHTML = '';
        await loadChatHistory();
        appendMessageToChat('system', `Switched to ${currentAigent.name}.`, new Date().toISOString(), true, 'info');

    } catch (error) {
        console.error("Failed to switch aigent:", error);
        appendMessageToChat('system', `Error switching aigent: ${error.message}`, new Date().toISOString(), true, 'error');
        selector.value = currentAigent.id; // Revert selector to old value on failure
        // Revert name display on failure as well
        if (aigentNameDisplay) aigentNameDisplay.textContent = currentAigent.name;
    } finally {
        const settingsMenu = document.getElementById('settings-menu');
        if (settingsMenu) settingsMenu.classList.remove('active');
    }
}


// --- NEW: TAB MANAGEMENT ---
function initializeTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    tabLinks.forEach(link => {
        link.addEventListener('click', switchTab);
    });
}

function switchTab(event) {
    const clickedTab = event.currentTarget;
    const tabId = clickedTab.dataset.tab;

    // Remove active state from all tabs and panes
    document.querySelectorAll('.tab-link').forEach(link => link.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

    // Add active state to the clicked tab and corresponding pane
    clickedTab.classList.add('active');
    document.getElementById(tabId).classList.add('active');

    // Special handling for calendar tab
    if (tabId === 'calendar') {
        renderCalendar(); // Always re-render calendar on tab click to ensure it's fresh
    }
}


// --- UPDATED: CALENDAR RENDERING ---
async function renderCalendar() {
    const container = document.getElementById('calendar-events-container');
    if (!container) return;

    container.innerHTML = '<em>Loading events...</em>'; // Show loading state

    try {
        const events = await apiFetch('/api/v1/calendar/events/');
        container.innerHTML = ''; // Clear loading state

        if (!events || events.length === 0) {
            container.innerHTML = `<div class="no-events-message">No calendar events found.</div>`;
            return;
        }
        
        const eventsList = document.createElement('div');
        eventsList.id = 'calendar-events';
        
        // No need to sort, API should return them ordered
        events.forEach(event => {
            const eventItem = document.createElement('div');
            eventItem.className = 'calendar-event-item';

            const title = document.createElement('h3');
            title.textContent = event.title || 'Untitled Event';
            
            const time = document.createElement('div');
            time.className = 'event-time';
            // This correctly displays the UTC time in the user's local browser timezone
            const startTime = new Date(event.start_time).toLocaleString();
            const endTime = new Date(event.end_time).toLocaleString();
            time.textContent = `${startTime} - ${endTime}`;

            const description = document.createElement('p');
            description.className = 'event-description';
            description.textContent = event.description || 'No description provided.';
            
            eventItem.append(title, time, description);
            eventsList.appendChild(eventItem);
        });
        
        container.appendChild(eventsList);

    } catch (error) {
        container.innerHTML = `<div class="no-events-message error">Failed to load calendar events: ${error.message}</div>`;
    }
}


// --- CHAT MESSAGE HANDLING ---

async function loadChatHistory() {
    const chatWindow = document.getElementById('chatWindow');
    const chatMessagesDiv = document.getElementById('chatMessages');
    if (!chatMessagesDiv || !chatWindow) return;
    chatMessagesDiv.innerHTML = '';
    try {
        const data = await apiFetch('/api/v1/chat/history/');
        if (data.history && Array.isArray(data.history)) {
            data.history.forEach(msg => appendMessageToChat(msg.role, msg.content, msg.timestamp, false));
            scrollToBottom(chatWindow);
        }
    } catch (error) {
        appendMessageToChat('system', `Error loading chat history: ${error.message}`, new Date().toISOString(), true, 'error');
    }
}

function appendMessageToChat(role, text, timestamp, doScroll = true, type = 'normal') {
    const chatWindow = document.getElementById('chatWindow');
    const chatMessagesDiv = document.getElementById('chatMessages');
    if (!chatMessagesDiv || !chatWindow) return;

    let normalizedRole = role.toLowerCase();
    const messageWrapper = document.createElement('div');
    messageWrapper.classList.add('message');

    if (normalizedRole === 'aigent' || normalizedRole === 'assistant') {
        normalizedRole = 'aigent';
        messageWrapper.classList.add('aigent');
    } else if (normalizedRole === 'user') {
        messageWrapper.classList.add('user');
    } else {
        messageWrapper.classList.add('system');
    }

    // Apply status styles (e.g., for error messages)
    if (type === 'error') messageWrapper.classList.add('error');
    if (type === 'info') messageWrapper.classList.add('info');

    if (normalizedRole === 'aigent') {
        // Render Aigent message based on its presentation format
        switch (currentAigent.presentationFormat) {
            case 'html':
                renderHtmlWidget(messageWrapper, text);
                break;
            case 'markdown':
                const markdownContentDiv = document.createElement('div');
                markdownContentDiv.className = 'markdown-content';
                markdownContentDiv.innerHTML = DOMPurify.sanitize(marked.parse(text));
                markdownContentDiv.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
                messageWrapper.appendChild(markdownContentDiv);
                break;
            case 'raw':
            default:
                const rawContentDiv = document.createElement('div');
                rawContentDiv.className = 'markdown-content';
                rawContentDiv.textContent = text;
                messageWrapper.appendChild(rawContentDiv);
                break;
        }
    } else {
        // For 'user' or 'system' messages, just display plain text
        const contentDiv = document.createElement('div');
        contentDiv.className = 'markdown-content';
        contentDiv.textContent = text;
        messageWrapper.appendChild(contentDiv);
    }
    
    chatMessagesDiv.appendChild(messageWrapper);
    if (doScroll) {
        setTimeout(() => scrollToBottom(chatWindow), 50);
    }
}

async function sendMessageToAigent(messageText, userId) { // Pass user ID
    const typingIndicator = document.getElementById('typingIndicator');
    const chatWindow = document.getElementById('chatWindow');

    if (typingIndicator) typingIndicator.style.display = 'block';
    if (chatWindow) scrollToBottom(chatWindow);

    try {
        // The celery task gets the user ID from the Django request now, so no need to send it.
        const taskData = await apiFetch('/api/v1/chat/send_message/', {
            method: 'POST',
            body: JSON.stringify({ message: messageText })
        });
        if (taskData && taskData.task_id) {
            pollTaskStatus(taskData.task_id, userId); // Pass user ID to poller
        } else {
            throw new Error("No task_id received from the server.");
        }
    } catch (error) {
        appendMessageToChat('system', `Error sending message: ${error.message}`, new Date().toISOString(), true, 'error');
        if (typingIndicator) typingIndicator.style.display = 'none';
    }
}

async function pollTaskStatus(taskId, userId, retries = 20, interval = 3000) { // Receive userId
    const typingIndicator = document.getElementById('typingIndicator');
    try {
        const data = await apiFetch(`/api/v1/chat/task_status/${taskId}/`);
        if (!data) throw new Error("Received empty data from task status API.");

        if (data.status === 'SUCCESS') {
            if (typingIndicator) typingIndicator.style.display = 'none';
            if (data.result && data.result.answer_to_user) {
                appendMessageToChat('aigent', data.result.answer_to_user, new Date().toISOString());

                // After a tool might have run, refresh the calendar if it's the active tab
                if (document.getElementById('calendar').classList.contains('active')) {
                    renderCalendar();
                }

            } else {
                appendMessageToChat('system', 'Aigent responded but the answer was unclear.', new Date().toISOString(), true, 'error');
            }
        } else if (data.status === 'FAILURE') {
            if (typingIndicator) typingIndicator.style.display = 'none';
            appendMessageToChat('system', `Aigent processing failed: ${data.error_message || 'Unknown error'}`, new Date().toISOString(), true, 'error');
        } else if (['PENDING', 'STARTED', 'RETRY'].includes(data.status)) {
            if (retries > 0) {
                if (data.status === 'RETRY') {
                    appendMessageToChat('system', `Aigent is retrying...`, new Date().toISOString(), true, 'info');
                }
                setTimeout(() => pollTaskStatus(taskId, userId, retries - 1, interval), interval);
            } else {
                if (typingIndicator) typingIndicator.style.display = 'none';
                appendMessageToChat('system', 'Aigent processing timed out.', new Date().toISOString(), true, 'error');
            }
        } else {
            if (typingIndicator) typingIndicator.style.display = 'none';
            appendMessageToChat('system', `Unknown task status: ${data.status}`, new Date().toISOString(), true, 'error');
        }
    } catch (error) {
        if (typingIndicator) typingIndicator.style.display = 'none';
        appendMessageToChat('system', `Error checking Aigent status: ${error.message}`, new Date().toISOString(), true, 'error');
    }
}

// --- HTML WIDGET RENDERING ---
function renderHtmlWidget(messageWrapper, text) {
    messageWrapper.classList.add('html-content');

    const htmlRegex = /<html.*?>([\s\S]*)<\/html>/i;
    const htmlContent = htmlRegex.test(text) ? text : `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{margin:0;padding:15px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:#333;background:#fff;word-wrap:break-word;overflow-wrap:break-word;width:auto;height:auto;min-width:400px;box-sizing:border-box}*{box-sizing:border-box}img{max-width:100%;height:auto}pre{white-space:pre-wrap;word-wrap:break-word;max-width:100%}html,body{overflow:hidden}html{height:auto!important;width:auto!important}</style></head><body>${text}</body></html>`;

    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'html-widget-container';

    // Create placeholder for when widget is minimized
    const minimisedMessageDiv = document.createElement('div');
    minimisedMessageDiv.className = 'minimised-widget-message';
    minimisedMessageDiv.style.display = 'none';
    minimisedMessageDiv.innerHTML = `
        <span>Interactive message minimized.</span>
        <button class="widget-restore-btn" title="Restore Widget">↻ Restore</button>
    `;

    // Create controls
    const copyBtn = document.createElement('button'); copyBtn.className = 'widget-copy-btn'; copyBtn.title = 'Copy HTML Source'; copyBtn.innerHTML = '📋';
    const refreshBtn = document.createElement('button'); refreshBtn.className = 'widget-refresh-btn'; refreshBtn.title = 'Refresh Widget'; refreshBtn.innerHTML = '↻';
    const stopBtn = document.createElement('button'); stopBtn.className = 'widget-stop-btn'; stopBtn.title = 'Minimize Widget'; stopBtn.innerHTML = '■';
    const iframe = document.createElement('iframe');
    iframe.setAttribute('frameborder', '0');
    iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms');

    // Define actions
    const restoreAction = () => {
        if (copyBtn.innerHTML !== '📋') copyBtn.innerHTML = '📋';
        minimisedMessageDiv.style.display = 'none';
        widgetContainer.style.display = 'block';
        iframe.srcdoc = htmlContent; // Reload content
    };

    // Assign event listeners
    copyBtn.onclick = () => { navigator.clipboard.writeText(htmlContent).then(() => { copyBtn.innerHTML = '✅'; setTimeout(() => { copyBtn.innerHTML = '📋'; }, 2000); }).catch(err => { copyBtn.innerHTML = '❌'; setTimeout(() => { copyBtn.innerHTML = '📋'; }, 2000); }); };
    refreshBtn.onclick = restoreAction;
    minimisedMessageDiv.querySelector('.widget-restore-btn').onclick = restoreAction;
    stopBtn.onclick = () => {
        iframe.srcdoc = ''; // Clear content to stop scripts
        widgetContainer.style.display = 'none';
        minimisedMessageDiv.style.display = 'flex';
    };
    
    setupAutoResizingIframe(iframe, htmlContent);

    widgetContainer.append(copyBtn, refreshBtn, stopBtn, iframe);
    messageWrapper.appendChild(widgetContainer);
    messageWrapper.appendChild(minimisedMessageDiv);
}

function setupAutoResizingIframe(iframe, htmlContent) {
    iframe.style.border = 'none';
    iframe.style.display = 'block';
    iframe.setAttribute('scrolling', 'no');
    iframe.srcdoc = htmlContent;

    let isResizing = false;
    let isInitialLoad = true;

    const resizeIframe = (iframeEl, shouldScroll) => {
        if (isResizing) return;
        isResizing = true;

        try {
            const iframeDoc = iframeEl.contentDocument || iframeEl.contentWindow.document;
            if (iframeDoc && iframeDoc.body) {
                // Short delay to allow content to render
                setTimeout(() => {
                    try {
                        const html = iframeDoc.documentElement;
                        const newHeight = html.scrollHeight;
                        const newWidth = html.scrollWidth;

                        const minHeight = 150, maxHeight = window.innerHeight * 0.8;
                        const minWidth = 400, maxWidth = Math.min(window.innerWidth * 0.9, 1200); 
                        
                        const finalHeight = Math.min(Math.max(newHeight, minHeight), maxHeight);
                        const finalWidth = Math.min(Math.max(newWidth, minWidth), maxWidth);

                        iframeEl.style.height = finalHeight + 'px';
                        iframeEl.style.width = finalWidth + 'px';
                        
                        if (shouldScroll) {
                            const chatWindow = document.getElementById('chatWindow');
                            if (chatWindow) setTimeout(() => scrollToBottom(chatWindow), 50);
                        }
                    } catch (e) { console.warn("Error during iframe dimension calculation:", e); } 
                    finally { isResizing = false; }
                }, 150);
            } else { isResizing = false; }
        } catch (e) {
            console.warn("Could not access iframe content for resizing:", e);
            isResizing = false;
        }
    };

    let debounceTimeout;
    const debouncedResize = (iframeEl) => {
        clearTimeout(debounceTimeout);
        debounceTimeout = setTimeout(() => resizeIframe(iframeEl, false), 200);
    };

    iframe.onload = function() {
        setTimeout(() => resizeIframe(this, isInitialLoad), 100);
        isInitialLoad = false;
        try {
            const iframeDoc = this.contentDocument || this.contentWindow.document;
            if (iframeDoc && iframeDoc.body) {
                const observer = new MutationObserver(() => debouncedResize(this));
                observer.observe(iframeDoc.body, { childList: true, subtree: true, attributes: true });
            }
        } catch (e) {
            console.warn("Could not set up iframe mutation observer:", e);
        }
    };
}


// --- FORM HANDLERS ---
async function handleChangePassword(event) {
    event.preventDefault();
    const oldPasswordEl = document.getElementById('old_password');
    const newPassword1El = document.getElementById('new_password1');
    const newPassword2El = document.getElementById('new_password2');
    const statusElement = document.getElementById('passwordChangeStatus');

    const oldPassword = oldPasswordEl.value;
    const newPassword1 = newPassword1El.value;
    const newPassword2 = newPassword2El.value;

    if (!statusElement) return;
    statusElement.style.display = 'none';
    statusElement.textContent = '';
    statusElement.className = 'status-message';

    if (newPassword1 !== newPassword2) {
        statusElement.textContent = "New passwords do not match.";
        statusElement.classList.add('error');
        statusElement.style.display = 'block';
        return;
    }
    if (!newPassword1) {
        statusElement.textContent = "New password cannot be empty.";
        statusElement.classList.add('error');
        statusElement.style.display = 'block';
        return;
    }
    try {
        await apiFetch('/api/v1/auth/password/change/', {
            method: 'POST',
            body: JSON.stringify({
                old_password: oldPassword,
                new_password1: newPassword1,
                new_password2: newPassword2
            })
        });
        statusElement.textContent = "Password changed successfully!";
        statusElement.classList.add('success');
        if (oldPasswordEl) oldPasswordEl.value = '';
        if (newPassword1El) newPassword1El.value = '';
        if (newPassword2El) newPassword2El.value = '';
    } catch (error) {
        statusElement.textContent = `Error: ${error.message || 'Failed to change password.'}`;
        statusElement.classList.add('error');
    } finally {
        statusElement.style.display = 'block';
    }
}


// --- DOMContentLoaded EVENT LISTENER & ROUTING ---
document.addEventListener('DOMContentLoaded', function() {

    // --- Event Listeners ---
    document.getElementById('logoutButton')?.addEventListener('click', logout);
    document.getElementById('settings-menu-btn')?.addEventListener('click', (event) => {
        event.stopPropagation();
        document.getElementById('settings-menu')?.classList.toggle('active');
    });
    document.getElementById('aigent-selector')?.addEventListener('change', handleAigentSwitch);
    document.querySelectorAll('.theme-choice-btn').forEach(button => {
        button.addEventListener('click', () => applyTheme(button.dataset.themeSet));
    });

    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to permanently delete your chat history for this Aigent? This action cannot be undone.')) return;
            try {
                await apiFetch('/api/v1/chat/history/', { method: 'DELETE' });
                const chatMessagesDiv = document.getElementById('chatMessages');
                if (chatMessagesDiv) chatMessagesDiv.innerHTML = '';
                appendMessageToChat('system', 'Chat history has been cleared.', new Date().toISOString(), true, 'info');
                document.getElementById('settings-menu').classList.remove('active');
            } catch (error) {
                appendMessageToChat('system', `Error clearing history: ${error.message}`, new Date().toISOString(), true, 'error');
            }
        });
    }

    // Close settings menu if clicking outside
    window.addEventListener('click', (event) => {
        const settingsMenu = document.getElementById('settings-menu');
        const settingsMenuBtn = document.getElementById('settings-menu-btn');
        if (settingsMenu && settingsMenu.classList.contains('active')) {
            if (!settingsMenu.contains(event.target) && !settingsMenuBtn.contains(event.target)) {
                settingsMenu.classList.remove('active');
            }
        }
    });

    // --- Basic Client-Side Routing ---
    const accessToken = localStorage.getItem('accessToken');
    const currentPagePath = window.location.pathname;

    // If on a protected page (main chat, password change)
    if (currentPagePath.endsWith('/index.html') || currentPagePath === '/' || currentPagePath.endsWith('/password-change.html')) {
        if (!accessToken) {
            window.location.href = '/login.html'; // Redirect to login if not authenticated
        } else {
            // User is authenticated, proceed with setup
            setupPage();
            // Add form handler if on the password change page
            if (currentPagePath.endsWith('/password-change.html')) {
                document.getElementById('passwordChangeForm')?.addEventListener('submit', handleChangePassword);
            }
        }
    }
    // If on the login page
    else if (currentPagePath.endsWith('/login.html')) {
        if (accessToken) {
            window.location.href = '/index.html'; // Redirect to chat if already logged in
        }
        // The login form submission is handled by an inline script in login.html
    }
});