// App State
let currentUser = null;
let currentPayee = null;
let contacts = [];
let users = [];
let transactionHistory = [];
let timelineHistory = [];

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadUsers();
    loadContacts();
    loadTransactionHistory();
    loadTimelineHistory();
});

// Load users from API
async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        const data = await response.json();
        users = data.users;
        renderUsers();
    } catch (error) {
        console.error('Failed to load users:', error);
        showToast('Failed to load users', 'error');
    }
}

// Render users in selector
function renderUsers() {
    const userList = document.getElementById('user-list');
    userList.innerHTML = '';
    
    users.forEach(user => {
        const card = document.createElement('div');
        card.className = 'user-card';
        card.onclick = () => selectUser(user);
        
        const initials = user.name.split(' ').map(n => n[0]).join('');
        
        card.innerHTML = `
            <div class="user-card-avatar">${initials}</div>
            <div class="user-card-info">
                <div class="user-card-name">${user.name}</div>
                <div class="user-card-vpa">${user.vpa}</div>
            </div>
            <div class="user-card-balance">₹${user.balance.toFixed(2)}</div>
        `;
        
        userList.appendChild(card);
    });
}

// Select user
function selectUser(user) {
    currentUser = user;
    document.getElementById('current-user').textContent = `${user.name} • ${user.vpa}`;
    document.getElementById('user-avatar').textContent = user.name[0];
    showContactsScreen();
}

// Show user selector
function showUserSelector() {
    hideAllScreens();
    document.getElementById('user-selector-screen').style.display = 'block';
    document.getElementById('bottom-nav').style.display = 'none';
    // Refresh user list so balances reflect latest transactions
    loadUsers();
}

// Load contacts from API
async function loadContacts() {
    try {
        const response = await fetch('/api/contacts');
        const data = await response.json();
        contacts = data.contacts;
        renderContacts();
    } catch (error) {
        console.error('Failed to load contacts:', error);
        showToast('Failed to load contacts', 'error');
    }
}

// Render contacts grid
function renderContacts() {
    const grid = document.getElementById('contacts-grid');
    grid.innerHTML = '';
    
    contacts.forEach(contact => {
        const card = document.createElement('div');
        card.className = 'contact-card';
        card.onclick = () => selectContact(contact);
        
        card.innerHTML = `
            <div class="contact-avatar">${contact.avatar}</div>
            <div class="contact-name">${contact.name}</div>
            <div class="contact-bank">${contact.bank}</div>
        `;
        
        grid.appendChild(card);
    });
}

// Select contact to pay
function selectContact(contact) {
    if (!currentUser) {
        showToast('Please select a user first', 'error');
        showUserSelector();
        return;
    }
    
    currentPayee = contact;
    document.getElementById('payee-avatar').textContent = contact.avatar;
    document.getElementById('payee-name').textContent = contact.name;
    document.getElementById('payee-vpa').textContent = contact.vpa;
    document.getElementById('amount-input').value = '';
    document.getElementById('pin-input').value = '';
    showPaymentScreen();
}

// Set quick amount
function setAmount(amount) {
    document.getElementById('amount-input').value = amount;
}

// Process payment
async function processPayment() {
    if (!currentUser) {
        showToast('Please select a user first', 'error');
        showUserSelector();
        return;
    }
    
    const amount = parseFloat(document.getElementById('amount-input').value);
    const pin = document.getElementById('pin-input').value;
    
    // Basic validation only - let API handle business rules
    if (!amount || amount <= 0) {
        showToast('Please enter a valid amount', 'error');
        return;
    }
    
    if (!pin || pin.length < 4) {
        showToast('Please enter your UPI PIN', 'error');
        return;
    }
    
    // Show loading
    const payBtn = document.getElementById('pay-btn');
    payBtn.classList.add('loading');
    payBtn.disabled = true;
    
    // Clear previous timeline and show processing state
    showProcessingTimeline();
    
    try {
        const response = await fetch('/api/transaction', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                payer_vpa: currentUser.vpa,
                payee_vpa: currentPayee.vpa,
                amount: amount,
                pin: pin,
            }),
        });
        
        const data = await response.json();
        
        // Render timeline steps
        if (data.steps && data.steps.length > 0) {
            renderTimeline(data.steps, data.success, {
                payer: currentUser.vpa,
                payee: currentPayee.vpa,
                payeeName: currentPayee.name,
                amount: amount,
                txnId: data.txn_id
            });
            
            // Save timeline to history
            saveTimelineToHistory(data.steps, data.success, {
                payer: currentUser.vpa,
                payee: currentPayee.vpa,
                payeeName: currentPayee.name,
                amount: amount,
                txnId: data.txn_id
            });
        }
        
        if (data.success) {
            // Add to transaction history
            const transaction = {
                id: data.txn_id || Date.now().toString(),
                payee: currentPayee.name,
                payee_vpa: currentPayee.vpa,
                amount: amount,
                status: 'success',
                date: new Date().toISOString(),
            };
            transactionHistory.unshift(transaction);
            saveTransactionHistory();
            
            // Show success animation
            document.getElementById('success-amount').textContent = `₹${amount.toFixed(2)}`;
            document.getElementById('success-to').textContent = `to ${currentPayee.name}`;
            document.getElementById('success-overlay').classList.add('show');
            
            // Hide success overlay after 2 seconds
            setTimeout(() => {
                document.getElementById('success-overlay').classList.remove('show');
                showContactsScreen();
            }, 2000);
        } else {
            // Display the specific error message from API
            const errorMsg = data.details || data.error || 'Transaction failed';
            showToast(errorMsg, 'error');
        }
    } catch (error) {
        console.error('Transaction error:', error);
        showToast('Transaction failed. Please try again.', 'error');
        
        // Add to transaction history as failed
        const transaction = {
            id: Date.now().toString(),
            payee: currentPayee.name,
            payee_vpa: currentPayee.vpa,
            amount: amount,
            status: 'failed',
            date: new Date().toISOString(),
            error: error.message,
        };
        transactionHistory.unshift(transaction);
        saveTransactionHistory();
    } finally {
        payBtn.classList.remove('loading');
        payBtn.disabled = false;
    }
}

// Show processing timeline placeholder
function showProcessingTimeline() {
    const timelineContent = document.getElementById('timeline-content');
    timelineContent.innerHTML = `
        <div class="timeline-steps">
            <div class="timeline-step processing">
                <div class="timeline-dot">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                        <circle cx="12" cy="12" r="3" fill="currentColor"/>
                    </svg>
                </div>
                <div class="timeline-step-content">
                    <div class="timeline-step-header">
                        <div>
                            <div class="timeline-step-title">Initiating Transaction</div>
                            <div class="timeline-step-desc">Processing your payment request...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Get step type badge HTML
function getStepTypeBadge(stepType) {
    if (!stepType) return '';
    
    const badges = {
        'validation': '<span class="step-type-badge">Validate</span>',
        'reqpay': '<span class="step-type-badge reqpay">ReqPay</span>',
        'reqpay_npci': '<span class="step-type-badge reqpay">ReqPay</span>',
        'reqpay_debit': '<span class="step-type-badge reqpay">ReqPay</span><span class="step-type-badge debit">DEBIT</span>',
        'reqpay_credit': '<span class="step-type-badge reqpay">ReqPay</span><span class="step-type-badge credit">CREDIT</span>',
        'resppay_debit': '<span class="step-type-badge resppay">RespPay</span><span class="step-type-badge debit">DEBIT</span>',
        'resppay_credit': '<span class="step-type-badge resppay">RespPay</span><span class="step-type-badge credit">CREDIT</span>',
        'complete': '<span class="step-type-badge credit">Complete</span>',
        'error': '<span class="step-type-badge debit">Error</span>',
    };
    
    return badges[stepType] || '';
}

// Get flow direction indicator
function getFlowDirection(stepType) {
    const flows = {
        'reqpay': { from: 'Payment UI', to: 'Payer PSP' },
        'reqpay_npci': { from: 'Payer PSP', to: 'NPCI' },
        'reqpay_debit': { from: 'NPCI', to: 'Remitter Bank' },
        'resppay_debit': { from: 'Remitter Bank', to: 'NPCI' },
        'reqpay_credit': { from: 'NPCI', to: 'Beneficiary Bank' },
        'resppay_credit': { from: 'Beneficiary Bank', to: 'NPCI' },
    };
    
    const flow = flows[stepType];
    if (!flow) return '';
    
    return `
        <div class="flow-direction">
            <span class="from">${flow.from}</span>
            <span class="arrow">→</span>
            <span class="to">${flow.to}</span>
        </div>
    `;
}

// Render timeline with steps
function renderTimeline(steps, success, txnInfo) {
    const timelineContent = document.getElementById('timeline-content');
    
    // Create transaction summary
    const summaryHtml = `
        <div class="transaction-summary ${success ? '' : 'error'}">
            <div class="transaction-summary-header">
                <div class="transaction-summary-icon ${success ? 'success' : 'error'}">
                    ${success ? '✓' : '✕'}
                </div>
                <div class="transaction-summary-title">
                    <h3>${success ? 'Transaction Successful' : 'Transaction Failed'}</h3>
                    <span>${txnInfo.txnId || 'N/A'}</span>
                </div>
            </div>
            <div class="transaction-summary-details">
                <div class="summary-detail">
                    <div class="summary-detail-label">From</div>
                    <div class="summary-detail-value">${txnInfo.payer}</div>
                </div>
                <div class="summary-detail">
                    <div class="summary-detail-label">To</div>
                    <div class="summary-detail-value">${txnInfo.payeeName}</div>
                </div>
                <div class="summary-detail">
                    <div class="summary-detail-label">Amount</div>
                    <div class="summary-detail-value">₹${txnInfo.amount.toFixed(2)}</div>
                </div>
                <div class="summary-detail">
                    <div class="summary-detail-label">Steps</div>
                    <div class="summary-detail-value">${steps.length}</div>
                </div>
            </div>
        </div>
    `;
    
    // Create flow legend
    const legendHtml = `
        <div class="flow-legend">
            <div class="legend-item">
                <div class="legend-dot reqpay"></div>
                <span>ReqPay (Request)</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot resppay"></div>
                <span>RespPay (Response)</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot error"></div>
                <span>Error/Failed</span>
            </div>
        </div>
    `;
    
    // Create timeline steps
    let stepsHtml = '<div class="timeline-steps">';
    
    steps.forEach((step, index) => {
        const stepId = `step-${index}-${Date.now()}`;
        const xmlId = `xml-${index}-${Date.now()}`;
        
        const statusIcon = getStatusIcon(step.status, step.step_type);
        const timeStr = step.timestamp ? step.timestamp.split(' ')[1] : '';
        const stepTypeBadge = getStepTypeBadge(step.step_type);
        const flowDirection = getFlowDirection(step.step_type);
        const dataType = step.step_type ? `data-type="${step.step_type}"` : '';
        
        stepsHtml += `
            <div class="timeline-step ${step.status}" ${dataType}>
                <div class="timeline-dot">
                    ${statusIcon}
                </div>
                <div class="timeline-step-content">
                    <div class="timeline-step-header">
                        <div>
                            <div class="timeline-step-title-wrapper">
                                <span class="timeline-step-title">${escapeHtml(step.title)}</span>
                                ${stepTypeBadge}
                            </div>
                            <div class="timeline-step-desc">${escapeHtml(step.description)}</div>
                            ${flowDirection}
                        </div>
                        <div class="timeline-step-meta">
                            <span class="timeline-step-time">${timeStr}</span>
                            ${step.duration_ms ? `<span class="timeline-step-duration">${step.duration_ms}ms</span>` : ''}
                        </div>
                    </div>
                    ${step.xml ? `
                        <div class="timeline-xml">
                            <button class="timeline-xml-toggle" onclick="toggleXml('${xmlId}', this)">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                                    <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                                </svg>
                                View XML Message
                            </button>
                            <div class="xml-content" id="${xmlId}">
                                <pre>${highlightXml(step.xml)}</pre>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    });
    
    stepsHtml += '</div>';
    
    timelineContent.innerHTML = summaryHtml + legendHtml + stepsHtml;
}

// Get status icon SVG
function getStatusIcon(status, stepType) {
    // Icons based on step type
    const isReqPay = stepType && (stepType.includes('reqpay'));
    const isRespPay = stepType && (stepType.includes('resppay'));
    
    switch (status) {
        case 'success':
            if (isReqPay) {
                // Arrow right for requests
                return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>`;
            } else if (isRespPay) {
                // Arrow left for responses
                return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>`;
            }
            // Checkmark for other success
            return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <path d="M5 12l5 5L20 7" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>`;
        case 'error':
            return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
            </svg>`;
        case 'processing':
            return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="3" fill="currentColor"/>
            </svg>`;
        default:
            return `<svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="3" fill="currentColor"/>
            </svg>`;
    }
}

// Highlight XML syntax
function highlightXml(xml) {
    if (!xml) return '';
    
    // Escape HTML first
    let escaped = escapeHtml(xml);
    
    // Highlight tags
    escaped = escaped.replace(/(&lt;\/?)([\w:]+)/g, '$1<span class="xml-tag">$2</span>');
    
    // Highlight attributes
    escaped = escaped.replace(/(\s)([\w:]+)(=)/g, '$1<span class="xml-attr">$2</span>$3');
    
    // Highlight attribute values
    escaped = escaped.replace(/(=)(&quot;)([^&]*)(&quot;)/g, '$1$2<span class="xml-value">$3</span>$4');
    
    return escaped;
}

// Toggle XML visibility
function toggleXml(xmlId, button) {
    const xmlContent = document.getElementById(xmlId);
    if (xmlContent) {
        xmlContent.classList.toggle('show');
        button.classList.toggle('expanded');
        button.innerHTML = xmlContent.classList.contains('show') 
            ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
               </svg>
               Hide XML`
            : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
               </svg>
               View XML`;
    }
}

// Escape HTML characters
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Clear timeline
function clearTimeline() {
    const timelineContent = document.getElementById('timeline-content');
    timelineContent.innerHTML = `
        <div class="timeline-empty">
            <div class="timeline-empty-icon">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
                    <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
                </svg>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" class="arrow-icon">
                    <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.3"/>
                </svg>
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none">
                    <rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
                    <path d="M16 2v4M8 2v4M3 10h18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.3"/>
                </svg>
            </div>
            <p>Transaction steps will appear here</p>
            <span>Complete a payment to see the UPI flow with XML messages</span>
        </div>
    `;
    
    // Clear saved timeline history
    timelineHistory = [];
    localStorage.removeItem('timelineHistory');
}

// Save timeline to history
function saveTimelineToHistory(steps, success, txnInfo) {
    timelineHistory.unshift({
        steps,
        success,
        txnInfo,
        date: new Date().toISOString()
    });
    
    // Keep only last 10 timelines
    if (timelineHistory.length > 10) {
        timelineHistory = timelineHistory.slice(0, 10);
    }
    
    localStorage.setItem('timelineHistory', JSON.stringify(timelineHistory));
}

// Load timeline history
function loadTimelineHistory() {
    const stored = localStorage.getItem('timelineHistory');
    if (stored) {
        try {
            timelineHistory = JSON.parse(stored);
            // If there's a recent timeline, display it
            if (timelineHistory.length > 0) {
                const latest = timelineHistory[0];
                renderTimeline(latest.steps, latest.success, latest.txnInfo);
            }
        } catch (e) {
            timelineHistory = [];
        }
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const icon = document.getElementById('toast-icon');
    const messageEl = document.getElementById('toast-message');
    
    // Set icon based on type
    if (type === 'success') {
        icon.textContent = '✓';
        toast.className = 'toast success';
    } else if (type === 'error') {
        icon.textContent = '✕';
        toast.className = 'toast error';
    } else {
        icon.textContent = 'ℹ';
        toast.className = 'toast';
    }
    
    messageEl.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Screen navigation
function hideAllScreens() {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.style.display = 'none';
    });
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
}

function showContactsScreen() {
    if (!currentUser) {
        showUserSelector();
        return;
    }
    hideAllScreens();
    document.getElementById('contacts-screen').style.display = 'block';
    document.getElementById('bottom-nav').style.display = 'flex';
    document.querySelectorAll('.nav-item')[0].classList.add('active');
}

function showPaymentScreen() {
    hideAllScreens();
    document.getElementById('payment-screen').style.display = 'block';
    document.getElementById('bottom-nav').style.display = 'none';
}

function showHistoryScreen() {
    if (!currentUser) {
        showUserSelector();
        return;
    }
    hideAllScreens();
    document.getElementById('history-screen').style.display = 'block';
    document.getElementById('bottom-nav').style.display = 'flex';
    document.querySelectorAll('.nav-item')[1].classList.add('active');
    renderTransactionHistory();
}

// Transaction history
function loadTransactionHistory() {
    const stored = localStorage.getItem('transactionHistory');
    if (stored) {
        try {
            transactionHistory = JSON.parse(stored);
        } catch (e) {
            transactionHistory = [];
        }
    }
}

function saveTransactionHistory() {
    localStorage.setItem('transactionHistory', JSON.stringify(transactionHistory));
}

function renderTransactionHistory() {
    const historyList = document.getElementById('history-list');
    
    if (transactionHistory.length === 0) {
        historyList.innerHTML = `
            <div class="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
                    <path d="M12 7v5l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.3"/>
                </svg>
                <p>No transactions yet</p>
            </div>
        `;
        return;
    }
    
    historyList.innerHTML = '';
    
    transactionHistory.forEach(txn => {
        const item = document.createElement('div');
        item.className = 'history-item';
        
        const statusIcon = txn.status === 'success' ? '✓' : '✕';
        const statusClass = txn.status === 'success' ? 'success' : 'failed';
        const amountPrefix = txn.status === 'success' ? '-' : '';
        
        const date = new Date(txn.date);
        const dateStr = date.toLocaleDateString('en-IN', { 
            month: 'short', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        item.innerHTML = `
            <div class="history-icon ${statusClass}">${statusIcon}</div>
            <div class="history-info">
                <div class="history-name">${txn.payee}</div>
                <div class="history-date">${dateStr}</div>
            </div>
            <div class="history-amount ${statusClass}">
                ${amountPrefix}₹${txn.amount.toFixed(2)}
            </div>
        `;
        
        historyList.appendChild(item);
    });
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Enter key on amount input moves to PIN
    if (e.key === 'Enter' && document.activeElement.id === 'amount-input') {
        document.getElementById('pin-input').focus();
    }
    
    // Enter key on PIN input triggers payment
    if (e.key === 'Enter' && document.activeElement.id === 'pin-input') {
        processPayment();
    }
});

// === XML Preview and Edit Functions ===

let currentXMLData = null;

// Preview ReqPay XML before sending
async function previewReqPayXML() {
    if (!currentUser) {
        showToast('Please select a user first', 'error');
        showUserSelector();
        return;
    }
    
    const amount = parseFloat(document.getElementById('amount-input').value);
    const pin = document.getElementById('pin-input').value;
    
    // Validation
    if (!amount || amount <= 0) {
        showToast('Please enter a valid amount', 'error');
        return;
    }
    
    if (!pin || pin.length < 4) {
        showToast('Please enter your UPI PIN', 'error');
        return;
    }
    
    // Show loading on preview button
    const previewBtn = document.getElementById('preview-xml-btn');
    const originalContent = previewBtn.innerHTML;
    previewBtn.innerHTML = '<div class="btn-spinner" style="border-color: #14b8a6; border-top-color: transparent; width: 16px; height: 16px;"></div><span>Loading...</span>';
    previewBtn.disabled = true;
    
    try {
        const response = await fetch('/api/preview-reqpay', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                payer_vpa: currentUser.vpa,
                payee_vpa: currentPayee.vpa,
                amount: amount,
                pin: pin,
            }),
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Store the XML data
            currentXMLData = {
                xml: data.xml,
                txn_id: data.txn_id,
                msg_id: data.msg_id,
                metadata: data.metadata
            };
            
            // Show modal with XML
            document.getElementById('xml-editor').value = data.xml;
            document.getElementById('xml-txn-id').textContent = data.txn_id;
            document.getElementById('xml-modal').classList.add('show');
        } else {
            showToast(data.error || 'Failed to generate XML', 'error');
        }
    } catch (error) {
        console.error('Preview error:', error);
        showToast('Failed to generate XML preview', 'error');
    } finally {
        previewBtn.innerHTML = originalContent;
        previewBtn.disabled = false;
    }
}

// Close XML modal
function closeXMLModal() {
    document.getElementById('xml-modal').classList.remove('show');
    currentXMLData = null;
}

// Copy XML to clipboard
async function copyXMLToClipboard() {
    const xml = document.getElementById('xml-editor').value;
    try {
        await navigator.clipboard.writeText(xml);
        showToast('XML copied to clipboard', 'success');
    } catch (error) {
        console.error('Copy error:', error);
        showToast('Failed to copy XML', 'error');
    }
}

// Send edited XML
async function sendEditedXML() {
    const editedXML = document.getElementById('xml-editor').value;
    
    if (!editedXML || !editedXML.trim()) {
        showToast('XML cannot be empty', 'error');
        return;
    }
    
    // Show loading on send button
    const sendBtn = document.getElementById('send-xml-btn');
    sendBtn.classList.add('loading');
    sendBtn.disabled = true;
    
    // Close modal and show processing timeline
    closeXMLModal();
    showProcessingTimeline();
    
    try {
        const response = await fetch('/api/send-edited-reqpay', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                xml: editedXML,
                metadata: currentXMLData ? currentXMLData.metadata : {
                    payer_vpa: currentUser.vpa,
                    payee_vpa: currentPayee.vpa,
                    amount: parseFloat(document.getElementById('amount-input').value)
                }
            }),
        });
        
        const data = await response.json();
        
        // Render timeline steps
        if (data.steps && data.steps.length > 0) {
            const amount = currentXMLData?.metadata?.amount || parseFloat(document.getElementById('amount-input').value);
            renderTimeline(data.steps, data.success, {
                payer: currentUser.vpa,
                payee: currentPayee.vpa,
                payeeName: currentPayee.name,
                amount: amount,
                txnId: data.txn_id
            });
            
            // Save timeline to history
            saveTimelineToHistory(data.steps, data.success, {
                payer: currentUser.vpa,
                payee: currentPayee.vpa,
                payeeName: currentPayee.name,
                amount: amount,
                txnId: data.txn_id
            });
        }
        
        if (data.success) {
            const amount = currentXMLData?.metadata?.amount || parseFloat(document.getElementById('amount-input').value);
            
            // Add to transaction history
            const transaction = {
                id: data.txn_id || Date.now().toString(),
                payee: currentPayee.name,
                payee_vpa: currentPayee.vpa,
                amount: amount,
                status: 'success',
                date: new Date().toISOString(),
            };
            transactionHistory.unshift(transaction);
            saveTransactionHistory();
            
            // Show success animation
            document.getElementById('success-amount').textContent = `₹${amount.toFixed(2)}`;
            document.getElementById('success-to').textContent = `to ${currentPayee.name}`;
            document.getElementById('success-overlay').classList.add('show');
            
            // Hide success overlay after 2 seconds
            setTimeout(() => {
                document.getElementById('success-overlay').classList.remove('show');
                showContactsScreen();
            }, 2000);
        } else {
            // Display error
            const errorMsg = data.details || data.error || 'Transaction failed';
            showToast(errorMsg, 'error');
        }
    } catch (error) {
        console.error('Transaction error:', error);
        showToast('Transaction failed. Please try again.', 'error');
        
        // Add to transaction history as failed
        const transaction = {
            id: Date.now().toString(),
            payee: currentPayee.name,
            payee_vpa: currentPayee.vpa,
            amount: parseFloat(document.getElementById('amount-input').value),
            status: 'failed',
            date: new Date().toISOString(),
            error: error.message,
        };
        transactionHistory.unshift(transaction);
        saveTransactionHistory();
    } finally {
        sendBtn.classList.remove('loading');
        sendBtn.disabled = false;
        currentXMLData = null;
    }
}
