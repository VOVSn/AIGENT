// --- THEME MANAGEMENT ---
const THEMES = ['light', 'dark', 'memphis'];

function applyTheme(theme) {
    if (!THEMES.includes(theme)) return;

    // 1. Set theme on root element
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    // 2. Switch highlight.js stylesheet
    const lightThemeLink = document.getElementById('hljs-light-theme');
    const darkThemeLink = document.getElementById('hljs-dark-theme');
    if (lightThemeLink && darkThemeLink) {
        lightThemeLink.disabled = (theme === 'dark');
        darkThemeLink.disabled = (theme !== 'dark');
    }

    // 3. Update active class on theme choice buttons
    document.querySelectorAll('.theme-choice-btn').forEach(btn => {
        btn.classList.toggle('active-theme', btn.dataset.themeSet === theme);
    });
}

// Immediately invoked function to apply theme on script load
(function() {
    const savedTheme = localStorage.getItem('theme');
    applyTheme(savedTheme || THEMES[0]);
})();


// --- Utility Functions ---
function getCSRFToken() {
    const csrfElement = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return csrfElement ? csrfElement.value : null;
}

function scrollToBottom(element) {
    if (element) {
        element.scrollTop = element.scrollHeight;
    }
}

// --- Authentication & API ---
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
            // For 204 No Content, response.json() will fail, so handle it before
            if (response.status === 204) return null;
            const errorData = await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` }));
            throw new Error(errorData.detail || `API request failed: ${response.statusText} (${response.status})`);
        }
        if (response.status === 204) return null; // Handle No Content responses successfully
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

function logout(message = "You have been logged out.") {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('username');
    window.location.href = '/login/';
}

// --- Chat Page Specific Functions ---
function setupChatPage() {
    const messageForm = document.getElementById('messageForm');
    const messageInput = document.getElementById('messageInput');
    const usernameDisplay = document.getElementById('usernameDisplay');
    const storedUsername = localStorage.getItem('username');
    if (usernameDisplay && storedUsername) usernameDisplay.textContent = storedUsername;
    loadChatHistory();
    if (messageForm) {
        messageForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const messageText = messageInput.value.trim();
            if (messageText) {
                appendMessageToChat('user', messageText);
                messageInput.value = '';
                await sendMessageToAigent(messageText);
            }
        });
    }
}

async function loadChatHistory() {
    const chatWindow = document.getElementById('chatWindow');
    const chatMessagesDiv = document.getElementById('chatMessages');
    if (!chatMessagesDiv || !chatWindow) return;
    chatMessagesDiv.innerHTML = ''; 
    try {
        const data = await apiFetch('/api/v1/chat/history/');
        if (data && data.history && Array.isArray(data.history)) {
            data.history.forEach(msg => {
                appendMessageToChat(msg.role, msg.content, msg.timestamp, false);
            });
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
    const contentDiv = document.createElement('div');
    if (normalizedRole === 'aigent') {
        const dirtyHtml = marked.parse(text);
        contentDiv.innerHTML = DOMPurify.sanitize(dirtyHtml);
        contentDiv.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
    } else {
        contentDiv.textContent = text;
    }
    messageWrapper.appendChild(contentDiv);
    chatMessagesDiv.appendChild(messageWrapper);
    if (doScroll) {
        scrollToBottom(chatWindow);
    }
}

async function sendMessageToAigent(messageText) {
    const typingIndicator = document.getElementById('typingIndicator');
    const chatWindow = document.getElementById('chatWindow');
    if (typingIndicator) typingIndicator.style.display = 'block';
    if (chatWindow) scrollToBottom(chatWindow);
    try {
        const taskData = await apiFetch('/api/v1/chat/send_message/', {
            method: 'POST',
            body: JSON.stringify({ message: messageText })
        });
        if (taskData && taskData.task_id) {
            pollTaskStatus(taskData.task_id);
        } else {
            throw new Error("No task_id received from send_message API or invalid response.");
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
        } else if (data.status === 'RETRY') {
            appendMessageToChat('system', `Aigent is retrying processing... (Info: ${data.error_message || 'No details'})`, new Date().toISOString(), true, 'info');
            if (retries > 0) setTimeout(() => pollTaskStatus(taskId, retries - 1, interval), interval);
            else {
                if (typingIndicator) typingIndicator.style.display = 'none';
                appendMessageToChat('system', 'Aigent processing timed out after retries.', new Date().toISOString(), true, 'error');
            }
        } else if (data.status === 'PENDING' || data.status === 'STARTED') {
            if (retries > 0) setTimeout(() => pollTaskStatus(taskId, retries - 1, interval), interval);
            else {
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

// --- Password Change Page Specific Functions ---
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
    // --- Global Event Listeners Setup ---
    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) logoutButton.addEventListener('click', logout);

    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to permanently delete your chat history? This action cannot be undone.')) {
                return;
            }
            try {
                await apiFetch('/api/v1/chat/history/', { method: 'DELETE' });
                const chatMessagesDiv = document.getElementById('chatMessages');
                if (chatMessagesDiv) {
                    chatMessagesDiv.innerHTML = '';
                }
                appendMessageToChat('system', 'Chat history has been cleared.', new Date().toISOString(), true, 'info');
                document.getElementById('settings-menu').classList.remove('active');
            } catch (error) {
                console.error("Failed to clear history:", error);
                appendMessageToChat('system', `Error clearing history: ${error.message}`, new Date().toISOString(), true, 'error');
            }
        });
    }

    // Login page's standalone theme button
    const loginThemeBtn = document.querySelector('.container > .theme-toggle-button');
    if(loginThemeBtn) {
        const cycle = () => {
             const currentTheme = localStorage.getItem('theme') || 'light';
             const currentIndex = THEMES.indexOf(currentTheme);
             const nextIndex = (currentIndex + 1) % THEMES.length;
             applyTheme(THEMES[nextIndex]);
        };
        loginThemeBtn.addEventListener('click', cycle);
    }
    
    // --- Settings Menu Logic ---
    const settingsMenuBtn = document.getElementById('settings-menu-btn');
    const settingsMenu = document.getElementById('settings-menu');

    if (settingsMenuBtn && settingsMenu) {
        settingsMenuBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            settingsMenu.classList.toggle('active');
        });

        settingsMenu.querySelectorAll('.theme-choice-btn').forEach(button => {
            button.addEventListener('click', () => {
                applyTheme(button.dataset.themeSet);
            });
        });
    }

    window.addEventListener('click', (event) => {
        if (settingsMenu && settingsMenu.classList.contains('active')) {
            if (!settingsMenu.contains(event.target) && !settingsMenuBtn.contains(event.target)) {
                settingsMenu.classList.remove('active');
            }
        }
    });

    // --- Page Specific Setup ---
    const accessToken = localStorage.getItem('accessToken');
    const currentPagePath = window.location.pathname;

    if (currentPagePath.includes('/chat/')) {
        if (!accessToken) window.location.href = '/login/';
        else setupChatPage();
    } else if (currentPagePath.includes('/password-change/')) {
        if (!accessToken) window.location.href = '/login/';
        else {
            const username = localStorage.getItem('username');
            const usernameDisplayEl = document.getElementById('usernameDisplay');
            if (usernameDisplayEl && username) usernameDisplayEl.textContent = username;
            const pcForm = document.getElementById('passwordChangeForm');
            if (pcForm) pcForm.addEventListener('submit', handleChangePassword);
        }
    } else if (currentPagePath.includes('/login/')) {
        if (accessToken) window.location.href = '/chat/';
    }
});