/**
 * Smart Waste AI — Global scripts
 */

// Toast notifications
function ensureToastContainer() {
    let el = document.getElementById('toastContainer');
    if (!el) {
        el = document.createElement('div');
        el.id = 'toastContainer';
        el.className = 'toast-container';
        document.body.appendChild(el);
    }
    return el;
}

window.toast = function (message, type) {
    type = type || 'success';
    const container = ensureToastContainer();
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () {
        toast.remove();
    }, 3500);
};

// Logout
document.addEventListener('DOMContentLoaded', function () {
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function () {
            fetch('/api/logout', { method: 'POST' })
                .then(function () {
                    window.location.href = '/login';
                });
        });
    }
});
