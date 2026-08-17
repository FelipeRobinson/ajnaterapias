const bar = document.querySelector('.topbar');
const menu = document.querySelector('#menu');
const links = document.querySelectorAll('#menu .nav-link');
const sections = [...links]
    .map(link => document.querySelector(link.getAttribute('href')))
    .filter(Boolean);

links.forEach(link => link.addEventListener('click', () => {
    links.forEach(item => item.classList.remove('is-active'));
    link.classList.add('is-active');
    if (window.matchMedia('(max-width: 767.98px)').matches) {
        bootstrap.Offcanvas.getOrCreateInstance(menu).hide();
    }
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
