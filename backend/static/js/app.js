document.addEventListener('DOMContentLoaded', function() {
    const accessToken = localStorage.getItem('accessToken');
    const username = localStorage.getItem('username');

    // If on chat page, check token and initialize
    if (window.location.pathname.includes('/chat/')) {
        if (!accessToken) {
            window.location.href = '/login/'; // Redirect to login if no token
            return;
        }
        document.getElementById('usernameDisplay').textContent = username || 'User';
        initializeChat();
    }

    // Logout functionality
    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) {
        logoutButton.addEventListener('click', logout);
    }
    
    // Password change functionality
    const passwordChangeForm = document.getElementById('passwordChangeForm');
    if (passwordChangeForm) {
        passwordChangeForm.addEventListener('submit', handleChangePassword);
    }
});

function initializeChat() {
    const messageForm = document.getElementById('messageForm');
    const messageInput = document.getElementById('messageInput');
    
    loadChatHistory();

    messageForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const messageText = messageInput.value.trim();
        if (messageText) {
            appendMessage('user', messageText);
            messageInput.value = '';
            await sendMessageToAigent(messageText);
        }
    });
}

async function apiFetch(url, options = {}) {
    const accessToken = localStorage.getItem('accessToken');
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
    }

    try {
        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) { // Unauthorized
            // Try to refresh token or redirect to login
            const refreshed = await refreshToken();
            if (refreshed) {
                // Retry original request with new token
                headers['Authorization'] = `Bearer ${localStorage.getItem('accessToken')}`;
                const retryResponse = await fetch(url, { ...options, headers });
                if (!retryResponse.ok) {
                    // If retry also fails, or for other non-401 errors from original request
                    const errorData = await retryResponse.json().catch(() => ({ detail: `HTTP error ${retryResponse.status}` }));
                    throw new Error(errorData.detail || `API request failed with status ${retryResponse.status}`);
                }
                return await retryResponse.json();
            } else {
                logout(); // Refresh failed, logout
                throw new Error("Session expired. Please login again.");
            }
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP error ${response.status}` }));
            throw new Error(errorData.detail || `API request failed with status ${response.status}`);
        }
        // For 202 Accepted, response might not have JSON body or it might be empty
        if (response.status === 202 || response.status === 204) { 
            return response; // Or some specific success indicator
        }
        return await response.json();
    } catch (error) {
        console.error('API Fetch Error:', error);
        // Display error to user or handle appropriately
        // For chat, might append an error message to chat window
        throw error; // Re-throw to be caught by calling function
    }
}


async function refreshToken() {
    const currentRefreshToken = localStorage.getItem('refreshToken');
    if (!currentRefreshToken) {
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
            // If your backend rotates refresh tokens, update it here:
            // if (data.refresh) localStorage.setItem('refreshToken', data.refresh);
            console.log("Token refreshed successfully");
            return true;
        }
        console.error("Failed to refresh token:", response.status);
        return false;
    } catch (error) {
        console.error("Error refreshing token:", error);
        return false;
    }
}


async function loadChatHistory() {
    const chatMessagesDiv = document.getElementById('chatMessages');
    chatMessagesDiv.innerHTML = ''; // Clear existing messages
    try {
        const data = await apiFetch('/api/v1/chat/history/');
        if (data.history && Array.isArray(data.history)) {
            data.history.forEach(msg => {
                appendMessage(msg.role, msg.content, msg.timestamp, false); // Don't scroll for initial load
            });
            scrollToBottom(chatMessagesDiv);
        }
    } catch (error) {
        console.error('Failed to load chat history:', error);
        appendMessage('system', `Error loading chat history: ${error.message}`, new Date().toISOString(), true, 'error');
    }
}

function appendMessage(role, text, timestamp, doScroll = true, type = 'normal') {
    const chatMessagesDiv = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', role.toLowerCase()); // e.g., 'message user', 'message aigent'
    if (type === 'error') messageDiv.style.color = 'red';

    const senderSpan = document.createElement('span');
    senderSpan.classList.add('sender');
    senderSpan.textContent = role === 'user' ? (localStorage.getItem('username') || 'You') : 'Aigent';
    
    const contentP = document.createElement('p');
    contentP.textContent = text;

    messageDiv.appendChild(senderSpan);
    messageDiv.appendChild(contentP);

    // Optional: Add timestamp display
    if (timestamp) {
        const timeSpan = document.createElement('span');
        timeSpan.style.fontSize = '0.7em';
        timeSpan.style.color = role === 'user' ? '#cce5ff' : '#6c757d';
        timeSpan.style.display = 'block';
        timeSpan.style.textAlign = role === 'user' ? 'right' : 'left';
        timeSpan.textContent = new Date(timestamp).toLocaleTimeString();
        // messageDiv.appendChild(timeSpan); // Or integrate it more nicely
    }


    chatMessagesDiv.appendChild(messageDiv);
    if (doScroll) {
        scrollToBottom(chatMessagesDiv);
    }
}

function scrollToBottom(element) {
    element.scrollTop = element.scrollHeight;
}

async function sendMessageToAigent(messageText) {
    const typingIndicator = document.getElementById('typingIndicator');
    typingIndicator.style.display = 'block';

    try {
        const response = await apiFetch('/api/v1/chat/send_message/', {
            method: 'POST',
            body: JSON.stringify({ message: messageText })
        });
        
        // Response for send_message is 202 Accepted, with task_id in body
        // but apiFetch for 202 returns the full response object.
        // We need to parse its body if it's not already done by apiFetch.
        let taskData;
        if (response.status === 202) {
            taskData = await response.json(); // Assuming 202 response has a JSON body
        } else { // Should have been handled by apiFetch error logic already
             throw new Error("Unexpected response from send_message");
        }
        
        if (taskData.task_id) {
            pollTaskStatus(taskData.task_id);
        } else {
            throw new Error("No task_id received from send_message API.");
        }

    } catch (error) {
        console.error('Failed to send message:', error);
        appendMessage('system', `Error sending message: ${error.message}`, new Date().toISOString(), true, 'error');
        typingIndicator.style.display = 'none';
    }
}

async function pollTaskStatus(taskId, retries = 20, interval = 3000) { // Poll for up to 60 seconds
    const typingIndicator = document.getElementById('typingIndicator');
    try {
        const data = await apiFetch(`/api/v1/chat/task_status/${taskId}/`);
        
        if (data.status === 'SUCCESS') {
            typingIndicator.style.display = 'none';
            if (data.result && data.result.answer_to_user) {
                appendMessage('aigent', data.result.answer_to_user, new Date().toISOString());
            } else {
                appendMessage('system', 'Aigent responded but the answer was unclear.', new Date().toISOString(), true, 'error');
            }
        } else if (data.status === 'FAILURE') {
            typingIndicator.style.display = 'none';
            appendMessage('system', `Aigent processing failed: ${data.error_message || 'Unknown error'}`, new Date().toISOString(), true, 'error');
        } else if (data.status === 'RETRY') {
            appendMessage('system', `Aigent is retrying processing... (${data.error_message || ''})`, new Date().toISOString(), true, 'info');
             if (retries > 0) {
                setTimeout(() => pollTaskStatus(taskId, retries - 1, interval), interval);
            } else {
                typingIndicator.style.display = 'none';
                appendMessage('system', 'Aigent processing timed out after retries.', new Date().toISOString(), true, 'error');
            }
        } else if (data.status === 'PENDING' || data.status === 'STARTED') {
            if (retries > 0) {
                setTimeout(() => pollTaskStatus(taskId, retries - 1, interval), interval);
            } else {
                typingIndicator.style.display = 'none';
                appendMessage('system', 'Aigent processing timed out.', new Date().toISOString(), true, 'error');
            }
        } else {
            typingIndicator.style.display = 'none';
            appendMessage('system', `Unknown task status: ${data.status}`, new Date().toISOString(), true, 'error');
        }
    } catch (error) {
        console.error(`Error polling task ${taskId}:`, error);
        typingIndicator.style.display = 'none';
        appendMessage('system', `Error checking Aigent status: ${error.message}`, new Date().toISOString(), true, 'error');
    }
}

function logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('username');
    window.location.href = '/login/';
}

async function handleChangePassword(event) {
    event.preventDefault();
    const oldPassword = document.getElementById('old_password').value;
    const newPassword1 = document.getElementById('new_password1').value;
    const newPassword2 = document.getElementById('new_password2').value;
    const statusElement = document.getElementById('passwordChangeStatus');

    statusElement.style.display = 'none';
    statusElement.textContent = '';
    statusElement.className = 'status-message'; // Reset class

    if (newPassword1 !== newPassword2) {
        statusElement.textContent = "New passwords do not match.";
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
        // Clear form fields
        document.getElementById('old_password').value = '';
        document.getElementById('new_password1').value = '';
        document.getElementById('new_password2').value = '';
    } catch (error) {
        statusElement.textContent = `Error: ${error.message || 'Failed to change password.'}`;
        statusElement.classList.add('error-message');
    } finally {
        statusElement.style.display = 'block';
    }
}