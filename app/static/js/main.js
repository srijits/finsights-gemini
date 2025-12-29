/**
 * AFXO Insights - Main JavaScript
 */

// Theme toggle - runs immediately to prevent flash
(function () {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = savedTheme || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
})();

// Theme toggle function
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

// Update theme toggle icon
function updateThemeIcon(theme) {
    // Handle public page icons
    const sunIcon = document.getElementById('theme-sun');
    const moonIcon = document.getElementById('theme-moon');
    // Handle admin page icons
    const adminSunIcon = document.getElementById('admin-theme-sun');
    const adminMoonIcon = document.getElementById('admin-theme-moon');

    if (theme === 'dark') {
        if (sunIcon) sunIcon.classList.remove('hidden');
        if (moonIcon) moonIcon.classList.add('hidden');
        if (adminSunIcon) adminSunIcon.style.display = 'inline';
        if (adminMoonIcon) adminMoonIcon.style.display = 'none';
    } else {
        if (sunIcon) sunIcon.classList.add('hidden');
        if (moonIcon) moonIcon.classList.remove('hidden');
        if (adminSunIcon) adminSunIcon.style.display = 'none';
        if (adminMoonIcon) adminMoonIcon.style.display = 'inline';
    }
}

// Initialize theme icon on page load
document.addEventListener('DOMContentLoaded', function () {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    updateThemeIcon(currentTheme);
});
// Sector tab filtering on homepage
document.addEventListener('DOMContentLoaded', function () {
    const sectorTabs = document.querySelectorAll('[data-sector]');
    const sectorCards = document.querySelectorAll('article[data-sector]');

    if (sectorTabs.length > 0 && sectorCards.length > 0) {
        sectorTabs.forEach(tab => {
            if (tab.classList.contains('tab')) {
                tab.addEventListener('click', function (e) {
                    e.preventDefault();

                    // Update active tab
                    sectorTabs.forEach(t => t.classList.remove('tab-active'));
                    this.classList.add('tab-active');

                    const sector = this.dataset.sector;

                    // Filter cards
                    sectorCards.forEach(card => {
                        if (sector === 'all' || card.dataset.sector === sector) {
                            card.style.display = '';
                        } else {
                            card.style.display = 'none';
                        }
                    });
                });
            }
        });
    }
});

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function () {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.5s';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
});

// Confirm before destructive actions
document.addEventListener('DOMContentLoaded', function () {
    const deleteButtons = document.querySelectorAll('[data-confirm]');
    deleteButtons.forEach(btn => {
        btn.addEventListener('click', function (e) {
            if (!confirm(this.dataset.confirm || 'Are you sure?')) {
                e.preventDefault();
            }
        });
    });
});

// Search input enhancement
document.addEventListener('DOMContentLoaded', function () {
    const searchInputs = document.querySelectorAll('input[name="q"], input[name="symbol"]');
    searchInputs.forEach(input => {
        // Auto-uppercase for symbol search
        if (input.name === 'symbol') {
            input.addEventListener('input', function () {
                this.value = this.value.toUpperCase();
            });
        }

        // Submit on Enter
        input.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                this.closest('form').submit();
            }
        });
    });
});

// Time ago formatting (optional enhancement)
function timeAgo(dateString) {
    if (!dateString) return '';

    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return interval === 1 ? `1 ${unit} ago` : `${interval} ${unit}s ago`;
        }
    }

    return 'Just now';
}

// Apply time ago to elements with data-time attribute
document.addEventListener('DOMContentLoaded', function () {
    const timeElements = document.querySelectorAll('[data-time]');
    timeElements.forEach(el => {
        const time = el.dataset.time;
        if (time) {
            el.textContent = timeAgo(time);
            el.title = new Date(time).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
        }
    });
});
