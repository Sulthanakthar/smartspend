/*
  SmartSpend Main JavaScript Module
  Handles Voice Speech-to-Text, Browser OCR, Chatbot, AJAX, and Client Translations
*/

let recognition = null;
let isRecording = false;
let silenceTimeout = null;
const SILENCE_DELAY = 1200; // 1.2 seconds of silence finishes recording
let accumulatedTranscript = '';

// 1. Voice Speech-to-Text Setup
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        document.getElementById('transcript-display').innerText = "Web Speech API is not supported in this browser. Please use Chrome or Edge.";
        return null;
    }

    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = langCode === 'hi' ? 'hi-IN' : langCode === 'es' ? 'es-ES' : langCode === 'fr' ? 'fr-FR' : 'en-US';

    rec.onstart = () => {
        isRecording = true;
        accumulatedTranscript = '';
        document.getElementById('mic-btn').classList.add('recording');
        document.getElementById('mic-icon').className = 'fa-solid fa-microphone-slash';
        document.getElementById('transcript-display').innerText = "Listening... Speak now.";
    };

    rec.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }

        // Show live visual stream of results
        const displayDiv = document.getElementById('transcript-display');
        if (displayDiv) {
            displayDiv.innerHTML = `<span style="color: var(--text-primary); font-weight: 500;">${accumulatedTranscript} ${finalTranscript}</span> <span style="color: var(--text-muted); font-style: italic;">${interimTranscript}</span>`;
        }

        if (finalTranscript) {
            accumulatedTranscript += ' ' + finalTranscript;
        }

        // High-performance voice detection: Reset timer on audio capture
        clearTimeout(silenceTimeout);
        silenceTimeout = setTimeout(() => {
            let textToProcess = (accumulatedTranscript + ' ' + interimTranscript).trim();
            if (textToProcess) {
                processVoiceTranscript(textToProcess);
                rec.stop();
            }
        }, SILENCE_DELAY);
    };

    rec.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        if (event.error !== 'no-speech') {
            document.getElementById('transcript-display').innerText = "Error capturing voice. Try again.";
            stopSpeechRecording();
        }
    };

    rec.onend = () => {
        stopSpeechRecording();
        clearTimeout(silenceTimeout);
    };

    return rec;
}

function toggleSpeechRecording() {
    if (!recognition) {
        recognition = initSpeechRecognition();
    }
    if (!recognition) return;

    if (isRecording) {
        recognition.stop();
    } else {
        recognition.start();
    }
}

function stopSpeechRecording() {
    isRecording = false;
    const btn = document.getElementById('mic-btn');
    const icon = document.getElementById('mic-icon');
    if (btn) btn.classList.remove('recording');
    if (icon) icon.className = 'fa-solid fa-microphone';
}

function processVoiceTranscript(text) {
    document.getElementById('transcript-display').innerText = `Processing: "${text}"`;

    // Post to NLP parsing endpoint
    fetch(apiParseVoiceUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ 'text': text })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('transcript-display').innerHTML =
                    `Detected: <strong style="color:var(--color-success);">${currencySymbol}${data.amount}</strong> for <strong>${data.category}</strong> (${data.description})`;

                // Open quick add modal and pre-fill details!
                openAddModal();
                document.getElementById('id_category').value = data.category;
                document.getElementById('id_description').value = data.description;
                document.getElementById('id_amount').value = data.amount;
            } else {
                document.getElementById('transcript-display').innerText = "Could not parse expense automatically. Please input manually.";
            }
        })
        .catch(err => {
            console.error("NLP processing error:", err);
            document.getElementById('transcript-display').innerText = "Network error. Try manually.";
        });
}

// 2. OCR Receipt Scanner Setup
function handleReceiptSelect(event) {
    const file = event.target.files[0];
    if (file) {
        processReceiptImage(file);
    }
}

function handleReceiptDrop(event) {
    event.preventDefault();
    document.getElementById('ocr-dropzone').style.borderColor = 'var(--border-color)';
    const file = event.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
        processReceiptImage(file);
    }
}

// Click trigger for dropzone
document.getElementById('ocr-dropzone')?.addEventListener('click', () => {
    document.getElementById('ocr-file-input').click();
});

function processReceiptImage(file) {
    const statusDiv = document.getElementById('ocr-status');
    if (statusDiv) {
        statusDiv.style.display = 'block';
        statusDiv.innerText = "Analyzing receipt with OCR...";
    }

    Tesseract.recognize(
        file,
        'eng',
        { logger: m => console.log(m) }
    ).then(({ data: { text } }) => {
        console.log("OCR Extracted Text:\n", text);
        if (statusDiv) statusDiv.style.display = 'none';

        // Simple OCR parser: find totals/decimals
        const amount = extractAmountFromOcr(text);

        if (amount > 0) {
            // Open manual add modal and autofill amount
            openAddModal();
            document.getElementById('id_amount').value = amount;
            document.getElementById('id_description').value = "Receipt Scan";
            document.getElementById('id_category').value = "Other"; // Default

            alert(`Receipt processed successfully! Extracted total amount: ${currencySymbol}${amount}`);
        } else {
            alert("OCR finished, but could not detect a clear transaction amount. Please input manually.");
            openAddModal();
            document.getElementById('id_description').value = "Receipt Scan";
        }
    }).catch(err => {
        console.error("OCR Error:", err);
        if (statusDiv) statusDiv.style.display = 'none';
        alert("Failed to analyze receipt. Check file formatting.");
    });
}

function extractAmountFromOcr(text) {
    // Look for lines with 'total', 'subtotal', 'due', 'amount'
    const lines = text.split('\n');
    let detectedAmount = 0.0;

    // Pattern to match decimals: e.g. 10.99, 1500.00
    const decimalRegex = /\b\d+\.\d{2}\b/;

    for (let line of lines) {
        const lowerLine = line.toLowerCase();
        if (lowerLine.includes('total') || lowerLine.includes('amount') || lowerLine.includes('net') || lowerLine.includes('due')) {
            const match = decimalRegex.exec(line);
            if (match) {
                const val = parseFloat(match[0]);
                if (val > detectedAmount) {
                    detectedAmount = val;
                }
            }
        }
    }

    // Fallback: If no keyword matches, just find the largest decimal number in the receipt
    if (detectedAmount === 0.0) {
        for (let line of lines) {
            const match = decimalRegex.exec(line);
            if (match) {
                const val = parseFloat(match[0]);
                if (val > detectedAmount) {
                    detectedAmount = val;
                }
            }
        }
    }

    return detectedAmount;
}

// 3. AI Chatbot Widget
function toggleChatbot() {
    const box = document.getElementById('chatbot-box');
    if (box) {
        box.classList.toggle('open');
        const icon = document.getElementById('chat-toggle-icon');
        if (box.classList.contains('open')) {
            icon.className = 'fa-solid fa-xmark';
        } else {
            icon.className = 'fa-solid fa-comments';
        }
    }
}

function handleChatKeypress(event) {
    if (event.key === 'Enter') {
        sendChatbotMessage();
    }
}

function sendChatbotMessage() {
    const input = document.getElementById('chatbot-input');
    const query = input.value.trim();
    if (!query) return;

    // Append user message
    appendChatMessage(query, 'user');
    input.value = '';

    // Send to server
    fetch(apiChatbotUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ 'query': query })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                appendChatMessage(data.response, 'bot');
                // Speak back the response!
                speakResponseText(data.response);
            } else {
                appendChatMessage("Sorry, I encountered an issue parsing your query.", 'bot');
            }
        })
        .catch(err => {
            console.error("Chatbot query error:", err);
            appendChatMessage("Network error. Could not connect to AI assistant.", 'bot');
        });
}

function appendChatMessage(text, sender) {
    const chatContainer = document.getElementById('chatbot-messages');
    const msg = document.createElement('div');
    msg.className = `chat-msg ${sender}`;

    // Render Markdown bold / bullet formatting
    let formattedText = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');

    msg.innerHTML = formattedText;
    chatContainer.appendChild(msg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Text-to-Speech synthesizer response speaker
function speakResponseText(text) {
    if ('speechSynthesis' in window) {
        // Strip markdown stars for reading
        const cleanText = text.replace(/\*/g, '').replace(/⚠️/g, 'warning').replace(/❌/g, 'limit exceeded');
        const utterance = new SpeechSynthesisUtterance(cleanText);

        // Speed preference
        utterance.rate = voiceRate;
        utterance.lang = langCode === 'hi' ? 'hi-IN' : langCode === 'es' ? 'es-ES' : langCode === 'fr' ? 'fr-FR' : 'en-US';

        window.speechSynthesis.speak(utterance);
    }
}

// 4. Modal dialogues controllers
function openAddModal() {
    document.getElementById('add-modal').classList.add('active');
}

function closeAddModal() {
    document.getElementById('add-modal').classList.remove('active');
}

function openEditModal(source, category, description, amount, date) {
    let idValue;
    let categoryValue;
    let descriptionValue;
    let amountValue;
    let dateValue;

    let targetEl = source;
    if (source && typeof source.closest === 'function') {
        const btn = source.closest('button');
        if (btn) {
            targetEl = btn;
        }
    }

    if (targetEl && typeof targetEl.getAttribute === 'function' && targetEl.getAttribute('data-expense-id')) {
        idValue = targetEl.getAttribute('data-expense-id');
        categoryValue = targetEl.getAttribute('data-category');
        descriptionValue = targetEl.getAttribute('data-description');
        amountValue = targetEl.getAttribute('data-amount');
        dateValue = targetEl.getAttribute('data-date');
    } else {
        idValue = source;
        categoryValue = category;
        descriptionValue = description;
        amountValue = amount;
        dateValue = date;
    }

    document.getElementById('edit-id').value = idValue || '';
    document.getElementById('edit-category').value = categoryValue || 'Food';
    document.getElementById('edit-description').value = descriptionValue || '';
    document.getElementById('edit-amount').value = amountValue || '';
    document.getElementById('edit-date').value = dateValue || '';
    document.getElementById('edit-modal').classList.add('active');
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('active');
}

// 5. Transaction CRUD handlers
function submitAddExpenseForm(event) {
    event.preventDefault();

    const category = document.getElementById('id_category').value;
    const description = document.getElementById('id_description').value;
    const amount = document.getElementById('id_amount').value;
    const date = document.getElementById('id_expense_date').value;

    // Offline Check
    if (!navigator.onLine) {
        const offlineQueue = JSON.parse(localStorage.getItem('offline_expense_queue') || '[]');
        offlineQueue.push({
            category: category,
            description: description,
            amount: amount,
            expense_date: date
        });
        localStorage.setItem('offline_expense_queue', JSON.stringify(offlineQueue));

        alert("⚠️ You are currently offline. Your transaction has been saved locally and will sync automatically when you reconnect!");
        closeAddModal();
        if (typeof showOfflineAlertBar === 'function') {
            showOfflineAlertBar();
        }
        return;
    }

    fetch(apiAddExpenseUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            'category': category,
            'description': description,
            'amount': amount,
            'expense_date': date
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddModal();
                window.location.reload(); // Reload to refresh metrics & charts instantly
            } else {
                alert(`Error adding transaction: ${data.error}`);
            }
        });
}

function submitEditExpenseForm(event) {
    event.preventDefault();

    const id = document.getElementById('edit-id').value;
    const category = document.getElementById('edit-category').value;
    const description = document.getElementById('edit-description').value;
    const amount = document.getElementById('edit-amount').value;
    const date = document.getElementById('edit-date').value;

    fetch(apiEditExpenseUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            'expense_id': id,
            'category': category,
            'description': description,
            'amount': amount,
            'expense_date': date
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditModal();
                window.location.reload();
            } else {
                alert(`Error updating transaction: ${data.error}`);
            }
        });
}

function deleteExpense(id) {
    if (confirm("Are you sure you want to delete this transaction?")) {
        fetch(apiDeleteExpenseUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ 'expense_id': id })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.reload();
                } else {
                    alert(`Error deleting transaction: ${data.error}`);
                }
            });
    }
}

// 6. Multi-language translator engine
const translations = {
    en: {
        dashboard: "Dashboard",
        history: "History",
        budgets: "Budgets",
        settings: "Settings",
        profile: "Profile",
        logout: "Logout",
    },
    es: {
        dashboard: "Panel",
        history: "Historial",
        budgets: "Presupuestos",
        settings: "Configuración",
        profile: "Perfil",
        logout: "Cerrar sesión",
    },
    fr: {
        dashboard: "Tableau",
        history: "Historique",
        budgets: "Budgets",
        settings: "Paramètres",
        profile: "Profil",
        logout: "Déconnexion",
    },
    hi: {
        dashboard: "डैशबोर्ड",
        history: "इतिहास",
        budgets: "बजट",
        settings: "सेटिंग्स",
        profile: "प्रोफाइल",
        logout: "लॉगआउट",
    }
};

function applyTranslations() {
    if (langCode === 'en') return;
    const trans = translations[langCode];
    if (!trans) return;

    // Find all elements with data-translate attribute
    document.querySelectorAll('[data-translate]').forEach(el => {
        const key = el.getAttribute('data-translate');
        if (trans[key]) {
            el.innerText = trans[key];
        }
    });
}

// Initialize translations
document.addEventListener("DOMContentLoaded", () => {
    applyTranslations();
});

// ─── Offline-First Sync Mechanisms ──────────────────────────────────────────
const apiSyncOfflineUrl = "/api/expense/sync/";

function showOfflineAlertBar() {
    let bar = document.getElementById('offline-sync-indicator');
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'offline-sync-indicator';
        bar.style.position = 'fixed';
        bar.style.top = '12px';
        bar.style.left = '50%';
        bar.style.transform = 'translateX(-50%)';
        bar.style.zIndex = '9999';
        bar.style.padding = '8px 20px';
        bar.style.borderRadius = '100px';
        bar.style.fontSize = '12px';
        bar.style.fontWeight = '700';
        bar.style.display = 'flex';
        bar.style.alignItems = 'center';
        bar.style.gap = '8px';
        bar.style.boxShadow = '0 10px 30px rgba(0,0,0,0.5)';
        bar.style.backdropFilter = 'blur(10px)';
        document.body.appendChild(bar);
    }

    const queue = JSON.parse(localStorage.getItem('offline_expense_queue') || '[]');
    if (queue.length > 0) {
        bar.style.background = 'rgba(245, 158, 11, 0.15)';
        bar.style.border = '1px solid rgba(245, 158, 11, 0.3)';
        bar.style.color = '#f59e0b';
        bar.innerHTML = `<i class="fa-solid fa-cloud-arrow-up fa-bounce"></i> Offline Mode (${queue.length} transactions pending sync)`;
        bar.style.display = 'flex';
    } else if (!navigator.onLine) {
        bar.style.background = 'rgba(239, 68, 68, 0.15)';
        bar.style.border = '1px solid rgba(239, 68, 68, 0.3)';
        bar.style.color = '#ef4444';
        bar.innerHTML = `<i class="fa-solid fa-wifi"></i> Offline Mode - No connection`;
        bar.style.display = 'flex';
    } else {
        bar.style.display = 'none';
    }
}

function syncOfflineQueue() {
    if (!navigator.onLine) return;
    const queue = JSON.parse(localStorage.getItem('offline_expense_queue') || '[]');
    if (queue.length === 0) {
        showOfflineAlertBar();
        return;
    }

    console.log('Connection restored. Syncing offline transactions...', queue);

    fetch(apiSyncOfflineUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ expenses: queue })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Offline queue synchronized successfully!');
                localStorage.removeItem('offline_expense_queue');
                showOfflineAlertBar();
                alert('🎉 Welcome back online! Your offline transactions have been synchronized successfully.');
                window.location.reload();
            } else {
                console.error('Error syncing offline queue:', data.error);
            }
        })
        .catch(err => {
            console.error('Network error during offline sync:', err);
        });
}

// Event Listeners for online/offline triggers
window.addEventListener('online', () => {
    syncOfflineQueue();
});

window.addEventListener('offline', () => {
    showOfflineAlertBar();
});

document.addEventListener("DOMContentLoaded", () => {
    // Initial check on load
    showOfflineAlertBar();
    if (navigator.onLine) {
        syncOfflineQueue();
    }
});
