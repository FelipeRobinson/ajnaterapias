const welcome = document.querySelector('[data-welcome-reveal]');
const welcomeTabs = [...document.querySelectorAll('[data-welcome-tab]')];
const welcomePanels = [...document.querySelectorAll('[data-welcome-panel]')];

if (welcome) {
    if ('IntersectionObserver' in window) {
        const welcomeObserver = new IntersectionObserver(entries => {
            if (!entries.some(entry => entry.isIntersecting)) return;
            welcome.classList.add('is-visible');
            welcomeObserver.disconnect();
        }, { threshold: .2 });

        welcomeObserver.observe(welcome);
    } else {
        welcome.classList.add('is-visible');
    }
}

const activateWelcomeTab = tab => {
    const target = tab.dataset.welcomeTab;

    welcomeTabs.forEach(item => {
        const isActive = item === tab;
        item.classList.toggle('is-active', isActive);
        item.setAttribute('aria-selected', isActive);
        item.tabIndex = isActive ? 0 : -1;
    });

    welcomePanels.forEach(panel => {
        const isActive = panel.dataset.welcomePanel === target;
        panel.classList.toggle('is-active', isActive);
        panel.hidden = !isActive;
    });
};

welcomeTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activateWelcomeTab(tab));
    tab.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;

        event.preventDefault();
        const direction = ['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1;
        const nextIndex = (index + direction + welcomeTabs.length) % welcomeTabs.length;
        welcomeTabs[nextIndex].focus();
        activateWelcomeTab(welcomeTabs[nextIndex]);
    });
});
