const historySection = document.querySelector('[data-history-reveal]');
const historyTabs = [...document.querySelectorAll('[data-history-tab]')];
const historyPanels = [...document.querySelectorAll('[data-history-panel]')];
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
let historyTimer;

function stopHistoryAutoplay() {
    window.clearInterval(historyTimer);
}

function startHistoryAutoplay() {
    stopHistoryAutoplay();
    if (prefersReducedMotion.matches || !historyTabs.length || document.hidden) return;

    historyTimer = window.setInterval(() => {
        const activeIndex = historyTabs.findIndex(tab => tab.classList.contains('is-active'));
        const nextIndex = (activeIndex + 1) % historyTabs.length;
        activateHistoryTab(historyTabs[nextIndex]);
    }, 6000);
}

if (historySection) {
    if ('IntersectionObserver' in window) {
        const historyObserver = new IntersectionObserver(entries => {
            if (!entries.some(entry => entry.isIntersecting)) return;
            historySection.classList.add('is-visible');
            startHistoryAutoplay();
            historyObserver.disconnect();
        }, { threshold: .2 });
        historyObserver.observe(historySection);
    } else {
        historySection.classList.add('is-visible');
        startHistoryAutoplay();
    }
}

const activateHistoryTab = tab => {
    const target = tab.dataset.historyTab;

    historyTabs.forEach(item => {
        const isActive = item === tab;
        item.classList.toggle('is-active', isActive);
        item.setAttribute('aria-selected', isActive);
        item.tabIndex = isActive ? 0 : -1;
    });

    historyPanels.forEach(panel => {
        const isActive = panel.dataset.historyPanel === target;
        panel.classList.toggle('is-active', isActive);
        panel.hidden = !isActive;
    });
};

historyTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => {
        activateHistoryTab(tab);
        startHistoryAutoplay();
    });
    tab.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
        event.preventDefault();
        const direction = ['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1;
        const next = historyTabs[(index + direction + historyTabs.length) % historyTabs.length];
        next.focus();
        activateHistoryTab(next);
        startHistoryAutoplay();
    });
});

historySection?.addEventListener('mouseenter', stopHistoryAutoplay);
historySection?.addEventListener('mouseleave', startHistoryAutoplay);
historySection?.addEventListener('focusin', stopHistoryAutoplay);
historySection?.addEventListener('focusout', event => {
    if (!historySection.contains(event.relatedTarget)) startHistoryAutoplay();
});

document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopHistoryAutoplay();
    else if (historySection?.classList.contains('is-visible')) startHistoryAutoplay();
});

prefersReducedMotion.addEventListener?.('change', startHistoryAutoplay);
