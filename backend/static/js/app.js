// Global state variables
let currentAigentName = 'LBA Prime Assistant';

// --- THEME MANAGEMENT ---
const THEMES = ['light', 'dark', 'memphis'];
function applyTheme(theme) {
    if (!THEMES.includes(theme)) return;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const lightThemeLink = document.getElementById('hljs-light-theme');
    const darkThemeLink = document.getElementById('hljs-dark-theme');
    if (lightThemeLink && darkThemeLink) {
        lightThemeLink.disabled = (theme === 'dark');
        darkThemeLink.disabled = (theme !== 'dark');
    }
    document.querySelectorAll('.theme-choice-btn').forEach(btn => {
        btn.classList.toggle('active-theme', btn.dataset.themeSet === theme);
    });
}
(function() { applyTheme(localStorage.getItem('theme') || THEMES[0]); })();

// --- Utility & API Functions ---
function scrollToBottom(element) { if (element) element.scrollTop = element.scrollHeight; }
async function apiFetch(url, options = {}) {
    let accessToken = localStorage.getItem('accessToken');
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
    try {
        let response = await fetch(url, { ...options, headers });
        if (response.status === 401 && url !== '/api/v1/auth/token/refresh/') {
            const refreshed = await refreshToken();
            if (refreshed) {
                accessToken = localStorage.getItem('accessToken');
                headers['Authorization'] = `Bearer ${accessToken}`;
                response = await fetch(url, { ...options, headers });
            } else {
                logout("Session expired. Please login again.");
                return Promise.reject(new Error("Session expired. Please login again."));
            }
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` }));
            throw new Error(errorData.detail || `API request failed: ${response.statusText} (${response.status})`);
        }
        if (response.status === 204) return null;
        return await response.json();
    } catch (error) {
        console.error('API Fetch General Error:', error.message);
        throw error;
    }
}
async function refreshToken() {
    const currentRefreshToken = localStorage.getItem('refreshToken');
    if (!currentRefreshToken) return false;
    try {
        const response = await fetch('/api/v1/auth/token/refresh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh: currentRefreshToken }) });
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('accessToken', data.access);
            return true;
        }
        return false;
    } catch (error) { return false; }
}
function logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('username');
    window.location.href = '/login/';
}

// --- Chat Page & Aigent Management ---
async function setupPage() {
    const username = localStorage.getItem('username');
    const usernameDisplayEl = document.getElementById('usernameDisplay');
    if (usernameDisplayEl && username) usernameDisplayEl.textContent = username;
    
    await populateAigentSelector();
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
                await sendMessageToAigent(messageText);
            }
        });
    }
}

async function populateAigentSelector() {
    const selector = document.getElementById('aigent-selector');
    if (!selector) return;
    try {
        const aigents = await apiFetch('/api/v1/aigents/list/');
        selector.innerHTML = '';
        aigents.forEach(aigent => {
            const option = document.createElement('option');
            option.value = aigent.id;
            option.textContent = aigent.name;
            if (aigent.is_active) {
                option.selected = true;
                currentAigentName = aigent.name;
            }
            selector.appendChild(option);
        });
    } catch (error) {
        console.error("Failed to populate aigents:", error);
    }
}

async function handleAigentSwitch(event) {
    const selector = event.target;
    const newAigentId = selector.value;
    const newAigent = selector.options[selector.selectedIndex].text;

    try {
        await apiFetch('/api/v1/aigents/set_active/', {
            method: 'POST',
            body: JSON.stringify({ aigent_id: newAigentId })
        });
        currentAigentName = newAigent;
        const chatMessagesDiv = document.getElementById('chatMessages');
        if (chatMessagesDiv) chatMessagesDiv.innerHTML = '';
        await loadChatHistory();
        appendMessageToChat('system', `Switched to ${currentAigentName}.`, new Date().toISOString(), true, 'info');
    } catch (error) {
        console.error("Failed to switch aigent:", error);
        appendMessageToChat('system', `Error switching aigent: ${error.message}`, new Date().toISOString(), true, 'error');
    } finally {
        const settingsMenu = document.getElementById('settings-menu');
        if (settingsMenu) settingsMenu.classList.remove('active');
    }
}

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

// Enhanced iframe auto-sizing function with message box resizing
function setupAutoResizingIframe(iframe, htmlContent) {
    // Set initial properties
    iframe.style.border = 'none';
    iframe.style.display = 'block';
    iframe.setAttribute('scrolling', 'no');
    iframe.srcdoc = htmlContent;

    let isResizing = false;
    let lastHeight = 0;
    let lastWidth = 0;
    let resizeAttempts = 0;
    const maxResizeAttempts = 5;

    const resizeIframe = (iframeEl) => {
        // Prevent multiple simultaneous resize operations
        if (isResizing) return;
        isResizing = true;

        try {
            const iframeDoc = iframeEl.contentDocument || iframeEl.contentWindow.document;
            if (iframeDoc && iframeDoc.body) {
                // Wait for content to fully render
                setTimeout(() => {
                    try {
                        const body = iframeDoc.body;
                        const html = iframeDoc.documentElement;
                        
                        // Remove any existing constraints temporarily
                        const originalBodyStyle = {
                            height: body.style.height,
                            width: body.style.width,
                            overflow: body.style.overflow
                        };
                        const originalHtmlStyle = {
                            height: html.style.height,
                            width: html.style.width,
                            overflow: html.style.overflow
                        };
                        
                        body.style.height = 'auto';
                        body.style.width = 'auto';
                        body.style.overflow = 'visible';
                        html.style.height = 'auto';
                        html.style.width = 'auto';
                        html.style.overflow = 'visible';
                        
                        // Force a reflow
                        body.offsetHeight;
                        body.offsetWidth;
                        
                        // Get content dimensions
                        const scrollHeight = Math.max(
                            body.scrollHeight || 0,
                            body.offsetHeight || 0,
                            html.clientHeight || 0,
                            html.scrollHeight || 0,
                            html.offsetHeight || 0
                        );
                        
                        const scrollWidth = Math.max(
                            body.scrollWidth || 0,
                            body.offsetWidth || 0,
                            html.clientWidth || 0,
                            html.scrollWidth || 0,
                            html.offsetWidth || 0
                        );
                        
                        // Get bounding box dimensions as additional check
                        let boundingHeight = 0;
                        let boundingWidth = 0;
                        try {
                            const rect = body.getBoundingClientRect();
                            boundingHeight = rect.height;
                            boundingWidth = rect.width;
                        } catch (e) {
                            boundingHeight = 0;
                            boundingWidth = 0;
                        }
                        
                        // Use the maximum of all measurements
                        const contentHeight = Math.max(scrollHeight, boundingHeight);
                        const contentWidth = Math.max(scrollWidth, boundingWidth);
                        
                        // Set constraints
                        const minHeight = 120;
                        const maxHeight = window.innerHeight * 0.8;
                        const minWidth = 300;
                        const maxWidth = Math.min(window.innerWidth * 0.9, 1200);
                        
                        const finalHeight = Math.min(Math.max(contentHeight + 10, minHeight), maxHeight);
                        const finalWidth = Math.min(Math.max(contentWidth + 10, minWidth), maxWidth);
                        
                        // Only update if dimensions have changed significantly
                        const heightDifference = Math.abs(finalHeight - lastHeight);
                        const widthDifference = Math.abs(finalWidth - lastWidth);
                        
                        if (heightDifference > 5 || widthDifference > 5 || lastHeight === 0 || lastWidth === 0) {
                            lastHeight = finalHeight;
                            lastWidth = finalWidth;
                            
                            // Set iframe dimensions ONLY. Let CSS handle the containers.
                            iframeEl.style.height = finalHeight + 'px';
                            iframeEl.style.width = finalWidth + 'px';
                            
                            console.log(`Iframe resized to: ${finalWidth}x${finalHeight}px (content: ${contentWidth}x${contentHeight}px)`);
                            
                            // Scroll chat to bottom after resize
                            const chatWindow = document.getElementById('chatWindow');
                            if (chatWindow) {
                                setTimeout(() => scrollToBottom(chatWindow), 100);
                            }
                        }

                        // Restore original styles
                        body.style.height = originalBodyStyle.height;
                        body.style.width = originalBodyStyle.width;
                        body.style.overflow = originalBodyStyle.overflow;
                        html.style.height = originalHtmlStyle.height;
                        html.style.width = originalHtmlStyle.width;
                        html.style.overflow = originalHtmlStyle.overflow;
                        
                    } catch (e) {
                        console.warn("Could not calculate iframe dimensions:", e);
                        // Fallback dimensions
                        if (lastHeight === 0 || lastWidth === 0) {
                            iframeEl.style.height = '200px';
                            iframeEl.style.width = '400px';
                            lastHeight = 200;
                            lastWidth = 400;
                        }
                    } finally {
                        isResizing = false;
                    }
                }, 150);
            } else {
                isResizing = false;
            }
        } catch (e) {
            console.warn("Could not auto-resize iframe:", e);
            // Fallback dimensions
            if (lastHeight === 0 || lastWidth === 0) {
                iframeEl.style.height = '200px';
                iframeEl.style.width = '400px';
                lastHeight = 200;
                lastWidth = 400;
            }
            isResizing = false;
        }
    };

    // Debounced resize function
    let resizeTimeout;
    const debouncedResize = (iframeEl) => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (resizeAttempts < maxResizeAttempts) {
                resizeAttempts++;
                resizeIframe(iframeEl);
            }
        }, 200);
    };

    // Handle iframe load event
    iframe.onload = function() {
        resizeAttempts = 0;
        
        // Initial resize with progressive delays
        setTimeout(() => resizeIframe(this), 100);
        setTimeout(() => resizeIframe(this), 300);
        setTimeout(() => resizeIframe(this), 600);
        
        // Set up observers for dynamic content
        try {
            const iframeDoc = this.contentDocument || this.contentWindow.document;
            if (iframeDoc && iframeDoc.body) {
                // Mutation observer
                const observer = new MutationObserver(() => {
                    debouncedResize(this);
                });
                
                observer.observe(iframeDoc.body, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeFilter: ['style', 'class', 'width', 'height']
                });
                
                // Window resize observer
                if (this.contentWindow) {
                    let windowResizeTimeout;
                    this.contentWindow.addEventListener('resize', () => {
                        clearTimeout(windowResizeTimeout);
                        windowResizeTimeout = setTimeout(() => {
                            debouncedResize(this);
                        }, 300);
                    });
                }
            }
        } catch (e) {
            console.warn("Could not set up iframe observers:", e);
        }
    };

    // Handle errors
    iframe.onerror = function() {
        console.error("Iframe failed to load");
        this.style.height = '200px';
        this.style.width = '400px';
        lastHeight = 200;
        lastWidth = 400;
    };
}

// Updated message appending function with HTML content class
function appendMessageToChat(role, text, timestamp, doScroll = true, type = 'normal') {
    const chatWindow = document.getElementById('chatWindow');
    const chatMessagesDiv = document.getElementById('chatMessages');
    if (!chatMessagesDiv || !chatWindow) return;

    let normalizedRole = role.toLowerCase();
    const messageWrapper = document.createElement('div');
    messageWrapper.classList.add('message', normalizedRole);

    if (normalizedRole === 'aigent' || normalizedRole === 'assistant') { 
        normalizedRole = 'aigent'; 
        messageWrapper.classList.add('aigent'); 
    } else if (normalizedRole === 'user') { 
        messageWrapper.classList.add('user'); 
    } else { 
        messageWrapper.classList.add('system'); 
    }

    if (type === 'error') messageWrapper.classList.add('error');
    if (type === 'info') messageWrapper.classList.add('info');

    if (normalizedRole === 'aigent' && currentAigentName === 'HTMLlo') {
        // Add HTML content class for special styling
        messageWrapper.classList.add('html-content');
        
        const htmlRegex = /<html.*?>([\s\S]*)<\/html>/i;
        let htmlContent;
        
        if (text.match(htmlRegex)) {
            htmlContent = text;
        } else {
            // Wrap non-HTML content with proper structure and auto-sizing styles
            htmlContent = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            margin: 0;
            padding: 15px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #fff;
            word-wrap: break-word;
            overflow-wrap: break-word;
            width: auto;
            height: auto;
            min-width: 250px;
            box-sizing: border-box;
        }
        * {
            box-sizing: border-box;
        }
        img {
            max-width: 100%;
            height: auto;
        }
        pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            max-width: 100%;
        }
        html, body {
            overflow-x: hidden;
            overflow-y: hidden;
        }
        /* Ensure content doesn't create unnecessary scrolling */
        html {
            height: auto !important;
            width: auto !important;
        }
    </style>
</head>
<body>${text}</body>
</html>`;
        }

        const widgetContainer = document.createElement('div');
        widgetContainer.className = 'html-widget-container';

        const copyBtn = document.createElement('button');
        copyBtn.className = 'widget-copy-btn';
        copyBtn.title = 'Copy HTML Source';
        copyBtn.innerHTML = '📋';
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(htmlContent).then(() => {
                copyBtn.innerHTML = '✅';
                setTimeout(() => { copyBtn.innerHTML = '📋'; }, 2000);
            }).catch(err => {
                console.error('Failed to copy HTML: ', err);
                copyBtn.innerHTML = '❌';
                setTimeout(() => { copyBtn.innerHTML = '📋'; }, 2000);
            });
        };

        const refreshBtn = document.createElement('button');
        refreshBtn.className = 'widget-refresh-btn';
        refreshBtn.title = 'Refresh Widget';
        refreshBtn.innerHTML = '↻';
        
        const iframe = document.createElement('iframe');
        iframe.setAttribute('frameborder', '0');
        iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms');
        
        // Set up auto-resizing with the enhanced function
        setupAutoResizingIframe(iframe, htmlContent);

        refreshBtn.onclick = () => { 
            if (copyBtn.innerHTML !== '📋') {
                copyBtn.innerHTML = '📋';
            }
            setupAutoResizingIframe(iframe, htmlContent);
        };

        widgetContainer.appendChild(copyBtn);
        widgetContainer.appendChild(refreshBtn);
        widgetContainer.appendChild(iframe);
        messageWrapper.appendChild(widgetContainer);

    } else if (normalizedRole === 'aigent') {
        const contentDiv = document.createElement('div');
        contentDiv.className = 'markdown-content';
        contentDiv.innerHTML = DOMPurify.sanitize(marked.parse(text));
        contentDiv.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
        messageWrapper.appendChild(contentDiv);
    } else {
        const contentDiv = document.createElement('div');
        contentDiv.className = 'markdown-content';
        contentDiv.textContent = text;
        messageWrapper.appendChild(contentDiv);
    }
    
    chatMessagesDiv.appendChild(messageWrapper);
    if (doScroll) {
        // Delay scroll to ensure iframe has time to resize
        setTimeout(() => scrollToBottom(chatWindow), 800);
    }
}

async function sendMessageToAigent(messageText) {
    const typingIndicator = document.getElementById('typingIndicator');
    const chatWindow = document.getElementById('chatWindow');
    if (typingIndicator) typingIndicator.style.display = 'block';
    if (chatWindow) scrollToBottom(chatWindow);
    try {
        const taskData = await apiFetch('/api/v1/chat/send_message/', { method: 'POST', body: JSON.stringify({ message: messageText }) });
        if (taskData && taskData.task_id) {
            pollTaskStatus(taskData.task_id);
        } else {
            throw new Error("No task_id received from send_message API.");
        }
    } catch (error) {
        appendMessageToChat('system', `Error sending message: ${error.message}`, new Date().toISOString(), true, 'error');
        if (typingIndicator) typingIndicator.style.display = 'none';
    }
}

async function pollTaskStatus(taskId, retries = 20, interval = 3000) {
    const typingIndicator = document.getElementById('typingIndicator');
    try {
        const data = await apiFetch(`/api/v1/chat/task_status/${taskId}/`);
        if (!data) throw new Error("Received null or undefined data from task status API.");
        if (data.status === 'SUCCESS') {
            if (typingIndicator) typingIndicator.style.display = 'none';
            if (data.result && data.result.answer_to_user) {
                appendMessageToChat('aigent', data.result.answer_to_user, new Date().toISOString());
            } else {
                appendMessageToChat('system', 'Aigent responded but the answer was unclear.', new Date().toISOString(), true, 'error');
            }
        } else if (data.status === 'FAILURE') {
            if (typingIndicator) typingIndicator.style.display = 'none';
            appendMessageToChat('system', `Aigent processing failed: ${data.error_message || 'Unknown error'}`, new Date().toISOString(), true, 'error');
        } else if (data.status === 'PENDING' || data.status === 'STARTED' || data.status === 'RETRY') {
            if (retries > 0) {
                if(data.status === 'RETRY') appendMessageToChat('system', `Aigent is retrying...`, new Date().toISOString(), true, 'info');
                setTimeout(() => pollTaskStatus(taskId, retries - 1, interval), interval);
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
        statusElement.classList.add('error-message');
        statusElement.style.display = 'block';
        return;
    }
    if (!newPassword1) {
        statusElement.textContent = "New password cannot be empty.";
        statusElement.classList.add('error-message');
        statusElement.style.display = 'block';
        return;
    }
    try {
        await apiFetch('/api/v1/auth/password/change/', {
            method: 'POST',
            body: JSON.stringify({ old_password: oldPassword, new_password1: newPassword1, new_password2: newPassword2 })
        });
        statusElement.textContent = "Password changed successfully!";
        statusElement.classList.add('success-message');
        if(oldPasswordEl) oldPasswordEl.value = '';
        if(newPassword1El) newPassword1El.value = '';
        if(newPassword2El) newPassword2El.value = '';
    } catch (error) {
        statusElement.textContent = `Error: ${error.message || 'Failed to change password.'}`;
        statusElement.classList.add('error-message');
    } finally {
        statusElement.style.display = 'block';
    }
}

// --- DOMContentLoaded Event Listener ---
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('logoutButton')?.addEventListener('click', logout);
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
    const settingsMenuBtn = document.getElementById('settings-menu-btn');
    const settingsMenu = document.getElementById('settings-menu');
    if (settingsMenuBtn && settingsMenu) {
        settingsMenuBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            settingsMenu.classList.toggle('active');
        });
    }
    document.querySelectorAll('.theme-choice-btn').forEach(button => {
        button.addEventListener('click', () => applyTheme(button.dataset.themeSet));
    });
    const aigentSelector = document.getElementById('aigent-selector');
    if (aigentSelector) aigentSelector.addEventListener('change', handleAigentSwitch);
    window.addEventListener('click', (event) => {
        if (settingsMenu && settingsMenu.classList.contains('active')) {
            if (!settingsMenu.contains(event.target) && !settingsMenuBtn.contains(event.target)) {
                settingsMenu.classList.remove('active');
            }
        }
    });

    const accessToken = localStorage.getItem('accessToken');
    const currentPagePath = window.location.pathname;
    if (currentPagePath.includes('/chat/') || currentPagePath.includes('/password-change/')) {
        if (!accessToken) window.location.href = '/login/';
        else {
            setupPage();
            if (currentPagePath.includes('/password-change/')) {
                document.getElementById('passwordChangeForm')?.addEventListener('submit', handleChangePassword);
            }
        }
    } else if (currentPagePath.includes('/login/')) {
        if (accessToken) window.location.href = '/chat/';
    }
});