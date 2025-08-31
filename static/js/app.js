// Main application JavaScript

// Global variables
let currentQuizAttempt = null;
let startTime = null;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            if (alert.classList.contains('alert-info') || alert.classList.contains('alert-success')) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        });
    }, 5000);
    
    // Initialize quiz timer if on quiz page
    if (document.querySelector('.quiz-question')) {
        startTime = Date.now();
        startQuizTimer();
    }
});

// Quiz functionality
function startQuizTimer() {
    const timerDisplay = document.getElementById('quiz-timer');
    if (!timerDisplay) return;
    
    setInterval(function() {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        timerDisplay.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }, 1000);
}

function submitQuizAnswer(questionId, questionNum, totalQuestions) {
    const selectedAnswer = document.querySelector('input[name="answer"]:checked') || 
                          document.querySelector('textarea[name="answer"]');
    const confidenceSlider = document.getElementById('confidenceSlider');
    const confidence = confidenceSlider ? confidenceSlider.value : 0.5;
    
    if (!selectedAnswer || !selectedAnswer.value.trim()) {
        showAlert('Please select or enter an answer', 'warning');
        return;
    }
    
    const responseTime = startTime ? Math.floor((Date.now() - startTime) / 1000) : 0;
    const hintsUsed = parseInt(document.getElementById('hints-used')?.textContent) || 0;
    
    // Disable form and show loading state
    const form = document.querySelector('.quiz-form');
    const submitBtn = document.querySelector('.btn-submit');
    const allInputs = form.querySelectorAll('input, textarea, button');
    allInputs.forEach(input => input.disabled = true);
    
    if (submitBtn) {
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Submitting...';
    }
    
    fetch('/quiz/submit_answer', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            question_id: questionId,
            answer: selectedAnswer.value.trim(),
            response_time: responseTime,
            hints_used: hintsUsed,
            confidence: confidence
        })
    })
    .then(response => response.json())
    .then(data => {
        showAnswerFeedback(data);
        
        // Immediately move to next question/completion
        if (questionNum === totalQuestions) {
            window.location.href = '/quiz/complete';
        } else {
            window.location.href = `/quiz/question/${questionNum + 1}`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('An error occurred while submitting your answer. Please try again.', 'danger');
        allInputs.forEach(input => input.disabled = false);
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="fas fa-check"></i> Submit Answer';
        }
    });
}

function showAnswerFeedback(data) {
    const feedbackContainer = document.getElementById('feedback-container');
    const feedbackAlert = document.getElementById('feedback-alert');
    const feedbackText = document.getElementById('feedback-text');
    
    if (data.correct) {
        feedbackAlert.className = 'alert alert-success';
        feedbackText.innerHTML = '<i class="fas fa-check-circle"></i> Correct! Well done.';
    } else {
        feedbackAlert.className = 'alert alert-danger';
        feedbackText.innerHTML = `<i class="fas fa-times-circle"></i> Incorrect. ${data.explanation || 'Try to review this concept.'}`;
    }
    
    feedbackContainer.style.display = 'block';
    feedbackContainer.scrollIntoView({ behavior: 'smooth' });
}

function getHint(questionId) {
    fetch(`/quiz/hint/${questionId}`)
        .then(response => response.json())
        .then(data => {
            const hintContainer = document.getElementById('hint-container');
            const hintText = document.getElementById('hint-text');
            
            hintText.textContent = data.hint;
            hintContainer.style.display = 'block';
            hintContainer.scrollIntoView({ behavior: 'smooth' });
            
            // Update hints used counter
            const hintsUsedElement = document.getElementById('hints-used');
            const currentHints = parseInt(hintsUsedElement.textContent) || 0;
            hintsUsedElement.textContent = currentHints + 1;
            
            // Disable hint button after use
            const hintBtn = document.querySelector('.btn-hint');
            if (hintBtn) {
                hintBtn.disabled = true;
                hintBtn.innerHTML = '<i class="fas fa-lightbulb"></i> Hint Used';
            }
        })
        .catch(error => {
            console.error('Error getting hint:', error);
            showAlert('Unable to get hint at the moment. Please try again.', 'warning');
        });
}

// Chat functionality
function initializeChat() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function sendChatMessage(sessionId) {
    const messageInput = document.getElementById('message-input');
    const message = messageInput.value.trim();
    
    if (!message) {
        messageInput.focus();
        return;
    }
    
    // Clear input and disable send button
    messageInput.value = '';
    const sendBtn = document.querySelector('.btn-send');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    }
    
    // Add user message to chat
    addMessageToChat('You', message, 'student');
    
    // Show typing indicator
    addTypingIndicator();
    
    fetch('/chat/send', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message: message,
            session_id: sessionId
        })
    })
    .then(response => response.json())
    .then(data => {
        removeTypingIndicator();
        addMessageToChat('AI Tutor', data.ai_response, 'ai');
        
        // Re-enable send button
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        }
        messageInput.focus();
    })
    .catch(error => {
        console.error('Chat error:', error);
        removeTypingIndicator();
        addMessageToChat('AI Tutor', 'Sorry, I encountered an error. Please try again.', 'ai');
        
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        }
        messageInput.focus();
    });
}

function addMessageToChat(sender, message, type) {
    const chatMessages = document.getElementById('chat-messages');
    const isStudent = type === 'student';
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message mb-3 ${isStudent ? 'text-end' : 'text-start'}`;
    messageDiv.innerHTML = `
        <div class="d-inline-block p-3 rounded ${isStudent ? 'bg-primary text-white' : 'bg-light border'}" style="max-width: 75%;">
            <strong>${sender}:</strong><br>
            ${escapeHtml(message)}
        </div>
        <small class="d-block text-muted mt-1">${new Date().toLocaleTimeString('en-US', {hour: '2-digit', minute:'2-digit'})}</small>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addTypingIndicator() {
    const chatMessages = document.getElementById('chat-messages');
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typing-indicator';
    typingDiv.className = 'message mb-3 text-start';
    typingDiv.innerHTML = `
        <div class="d-inline-block p-3 rounded bg-light border">
            <strong>AI Tutor:</strong><br>
            <span class="typing-dots">Thinking<span class="dots">...</span></span>
        </div>
    `;
    
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Utility functions
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container') || createAlertContainer();
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertContainer.appendChild(alertDiv);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            const bsAlert = new bootstrap.Alert(alertDiv);
            bsAlert.close();
        }
    }, 5000);
}

function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alert-container';
    container.className = 'position-fixed top-0 start-50 translate-middle-x mt-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTimeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes} minutes ago`;
    if (hours < 24) return `${hours} hours ago`;
    return `${days} days ago`;
}

// Progress tracking
function updateProgressChart(chartId, data) {
    const ctx = document.getElementById(chartId);
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'line',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Score: ' + context.parsed.y + '%';
                        }
                    }
                }
            }
        }
    });
}