// Main UI Interactivity & AJAX Handlers for SDERA Portal

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
}

// Close modal when clicking outside
window.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-backdrop')) {
        e.target.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
});

// Auto-dismiss flash alerts
document.addEventListener('DOMContentLoaded', () => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 6000);
    });
});

// Send Receipt Email via AJAX
async function emailReceiptAjax(receiptId, btnElement) {
    if (!btnElement) return;
    
    const originalText = btnElement.innerHTML;
    btnElement.disabled = true;
    btnElement.innerHTML = '✉️ Sending...';
    
    try {
        const response = await fetch(`/receipts/${receiptId}/email`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            btnElement.innerHTML = '✓ Sent!';
            btnElement.classList.remove('btn-outline-primary', 'btn-secondary');
            btnElement.classList.add('btn-success');
            showToast(data.message, 'success');
            setTimeout(() => {
                btnElement.innerHTML = originalText;
                btnElement.disabled = false;
                btnElement.classList.remove('btn-success');
            }, 3000);
        } else {
            btnElement.innerHTML = originalText;
            btnElement.disabled = false;
            showToast(data.message || 'Failed to dispatch email.', 'danger');
        }
    } catch (err) {
        btnElement.innerHTML = originalText;
        btnElement.disabled = false;
        showToast('Network error while requesting email dispatch.', 'danger');
    }
}

// Dynamically inject floating toast notification
function showToast(message, type = 'info') {
    let container = document.querySelector('.alerts-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'alerts-container';
        const wrapper = document.querySelector('.main-wrapper');
        if (wrapper) {
            wrapper.insertBefore(container, wrapper.firstChild);
        }
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <span>${message}</span>
        <button type="button" class="close-btn" onclick="this.parentElement.remove()">&times;</button>
    `;
    container.appendChild(alert);
    
    setTimeout(() => {
        alert.style.transition = 'opacity 0.5s ease';
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 500);
    }, 5000);
}

// Edit Member Modal population
function populateEditMember(id, name, email, phone, role, sqFeet) {
    const form = document.getElementById('editMemberForm');
    if (form) {
        form.action = `/admin/members/${id}/edit`;
        document.getElementById('edit_name').value = name;
        document.getElementById('edit_email').value = email;
        document.getElementById('edit_phone').value = phone;
        document.getElementById('edit_role').value = role;
        document.getElementById('edit_sq_feet').value = sqFeet;
        openModal('editMemberModal');
    }
}
