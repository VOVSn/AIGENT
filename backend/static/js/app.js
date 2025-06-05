// Global functions and event listeners
// Ensure this script is loaded after the DOM is ready, or wrap in DOMContentLoaded

// --- Utility Functions ---
function getCSRFToken() { // If ever needed for other types of Django forms
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
    let accessToken = localStorage.getItem('accessToken'); // Get fresh token each time
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
    }

    try {
        let response = await fetch(url, { ...options, headers });

        if (response.status === 401 && url !== '/api/v1/auth/token/refresh/') { // Unauthorized, and not a refresh failing
            console.log("Access token expired or invalid. Attempting refresh...");
            const refreshed = await refreshToken();
            if (refreshed) {
                accessToken = localStorage.getItem('accessToken'); // Get the new token
                headers['Authorization'] = `Bearer ${accessToken}`; // Update headers
                console.log("Retrying original request with new token...");
                response = await fetch(url, { ...options, headers }); // Retry original request
            } else {
                logout("Session expired. Please login again."); // Refresh failed
                return Promise.reject(new Error("Session expired. Please login again.")); // Stop further processing
            }
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` }));
            console.error(`API Error ${response.status} for ${url}:`, errorData);
            throw new Error(errorData.detail || `API request failed: ${response.statusText} (${response.status})`);
        }
        
        if (response.status === 204) { // No Content
            return null; 
        }
        // For 202 Accepted, it might or might not have a body. Assume it does for send_message.
        return await response.json();

    } catch (error) {
        console.error('API Fetch General Error:', error.message);
        throw error; // Re-throw to be caught by calling function
    }
}

async function refreshToken() {
    const currentRefreshToken = localStorage.getItem('refreshToken');
    if (!currentRefreshToken) {
        console.log("No refresh token available.");
        return false;
    }
    try {
        const response = await fetch('/api/v1/auth/token/refresh/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: currentRefreshToken })
        });
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('accessToken', data.access);
            // if (data.refresh) { localStorage.setItem('refreshToken', data.refresh); } // If backend rotates refresh tokens
            console.log("Token refreshed successfully.");
            return true;
        }
        console.error("Failed to refresh token:", response.status, await response.text());
        return false;
    } catch (error) {
        console.error("Error during token refresh:", error);
        return false;
    }
}

function logout(message = "You have been logged out.") {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('username');
    // alert(message); // Optional: notify user
    window.location.href = '/login/';
}

// --- Chat Page Specific Functions ---
function setupChatPage() {
    const messageForm = document.getElementById('messageForm');
    const messageInput = document.getElementById('messageInput');
    const usernameDisplay = document.getElementById('usernameDisplay');
    const storedUsername = localStorage.getItem('username');

    if (usernameDisplay && storedUsername) {
        usernameDisplay.textContent = storedUsername;
    }
    
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
    const chatMessagesDiv = document.getElementById('chatMessages');
    if (!chatMessagesDiv) return;
    chatMessagesDiv.innerHTML = ''; 
    try {
        const data = await apiFetch('/api/v1/chat/history/');
        if (data.history && Array.isArray(data.history)) {
            data.history.forEach(msg => {
                appendMessageToChat(msg.role, msg.content, msg.timestamp, false);
            });
            scrollToBottom(chatMessagesDiv);
        }
    } catch (error) {
        console.error('Failed to load chat history:', error.message);
        appendMessageToChat('system', `Error loading chat history: ${error.message}`, new Date().toISOString(), true, 'error');
    }
}

function appendMessageToChat(role, text, timestamp, doScroll = true, type = 'normal') {
    const chatMessagesDiv = document.getElementById('chatMessages');
    if (!chatMessagesDiv) return;

    const messageWrapper = document.createElement('div');
    messageWrapper.classList.add('message', role.toLowerCase());
    if (role === 'user') {
        messageWrapper.classList.add('user');
    } else if (role === 'aigent' || role === 'assistant') { // Handle 'assistant' role from backend
        messageWrapper.classList.add('aigent');
         role = 'aigent'; // Normalize role for class
    } else {
        messageWrapper.classList.add('system');
    }

    if (type === 'error') messageWrapper.classList.add('error');
    if (type === 'info') messageWrapper.classList.add('info');


    const contentP = document.createElement('p');
    contentP.textContent = text;
    messageWrapper.appendChild(contentP);

    // Optional: Add timestamp display if needed, current CSS hides .sender
    // if (timestamp) { ... }

    chatMessagesDiv.appendChild(messageWrapper);
    if (doScroll) {
        scrollToBottom(chatMessagesDiv);
    }
}

async function sendMessageToAigent(messageText) {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) typingIndicator.style.display = 'block';

    try {
        const taskData = await apiFetch('/api/v1/chat/send_message/', {
            method: 'POST',
            body: JSON.stringify({ message: messageText })
        });
        
        if (taskData && taskData.task_id) { // Ensure taskData is not null (e.g. from 204) and has task_id
            pollTaskStatus(taskData.task_id);
        } else {
            throw new Error("No task_id received from send_message API or invalid response.");
        }

    } catch (error) {
        console.error('Failed to send message:', error.message);
        appendMessageToChat('system', `Error sending message: ${error.message}`, new Date().toISOString(), true, 'error');
        if (typingIndicator) typingIndicator.style.display = 'none';
    }
}

async function pollTaskStatus(taskId, retries = 20, interval = 3000) {
    const typingIndicator = document.getElementById('typingIndicator');
    try {
        const data = await apiFetch(`/api/v1/chat/task_status/${taskId}/`);
        
        if (!data) { // Should not happen with current apiFetch if error handling is correct
            throw new Error("Received null or undefined data from task status API.");
        }

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
            if (retries > 0) {
                setTimeout(() => pollTaskStatus(taskId, retries - 1, interval), interval);
            } else {
                if (typingIndicator) typingIndicator.style.display = 'none';
                appendMessageToChat('system', 'Aigent processing timed out after retries.', new Date().toISOString(), true, 'error');
            }
        } else if (data.status === 'PENDING' || data.status === 'STARTED') {
            if (retries > 0) {
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
        console.error(`Error polling task ${taskId}:`, error.message);
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

    if (!statusElement) { console.error("Password status element not found"); return; }

    statusElement.style.display = 'none';
    statusElement.textContent = '';
    statusElement.className = 'status-message'; // Reset class

    if (newPassword1 !== newPassword2) {
        statusElement.textContent = "New passwords do not match.";
        statusElement.classList.add('error-message');
        statusElement.style.display = 'block';
        return;
    }
    if (!newPassword1) { // Basic validation
        statusElement.textContent = "New password cannot be empty.";
        statusElement.classList.add('error-message');
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
    const accessToken = localStorage.getItem('accessToken');
    const currentPagePath = window.location.pathname;

    // Generic Logout Button Handler (for any page that has it with this ID)
    const logoutButton = document.getElementById('logoutButton') || document.getElementById('logoutButtonGlobal');
    if (logoutButton) {
        logoutButton.addEventListener('click', logout);
    }

    if (currentPagePath.includes('/chat/')) {
        if (!accessToken) {
            window.location.href = '/login/'; // Redirect to login if no token
            return;
        }
        setupChatPage();
    } else if (currentPagePath.includes('/password-change/')) {
        if (!accessToken) {
            window.location.href = '/login/';
            return;
        }
        // Username display is handled by inline script in password_change.html for simplicity
        // or could be done here.
        const username = localStorage.getItem('username');
        const usernameDisplayEl = document.getElementById('usernameDisplay');
        if (usernameDisplayEl && username) {
            usernameDisplayEl.textContent = username;
        }

        const pcForm = document.getElementById('passwordChangeForm');
        if (pcForm) {
            pcForm.addEventListener('submit', handleChangePassword);
        }
    } else if (currentPagePath.includes('/login/')) {
        // If already logged in (e.g. token exists), redirect to chat
        if (accessToken) {
            window.location.href = '/chat/';
            return;
        }
        // Login form submission is handled by inline script in login.html
    }
});