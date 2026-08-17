const bar = document.querySelector('.topbar');
const toggle = document.querySelector('.topbar__toggle');
const links = document.querySelectorAll('.topbar__links a');
const menu = document.querySelector('.topbar__links');
const sections = [...links]
    .map(link => document.querySelector(link.getAttribute('href')))
    .filter(Boolean);

const closeMenu = () => {
    menu.classList.remove('is-open');
    toggle.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
};

toggle.addEventListener('click', () => {
    const isOpen = menu.classList.toggle('is-open');
    toggle.classList.toggle('is-open', isOpen);
    toggle.setAttribute('aria-expanded', String(isOpen));
});

links.forEach(link => link.addEventListener('click', () => {
    links.forEach(item => item.classList.remove('is-active'));
    link.classList.add('is-active');
    closeMenu();
}));

const updateActiveLink = () => {
    const line = bar.offsetHeight + window.innerHeight * .35;
    let active = sections[0];

    sections.forEach(section => {
        if (section.getBoundingClientRect().top <= line) active = section;
    });

    links.forEach(link => {
        link.classList.toggle('is-active', link.getAttribute('href') === `#${active.id}`);
    });
};

window.addEventListener('scroll', () => {
    bar.classList.toggle('is-scrolled', window.scrollY > 30);
    updateActiveLink();
}, { passive: true });

window.addEventListener('resize', updateActiveLink);
updateActiveLink();
