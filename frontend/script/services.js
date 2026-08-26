const serviceData = {
    acupuntura: {
        category: 'Medicina Tradicional Chinesa',
        name: 'Acupuntura',
        description: 'Utiliza agulhas muito finas em pontos específicos do corpo, definidos após uma escuta cuidadosa e uma avaliação energética individual.',
        note: 'Uma prática conduzida de forma individualizada e integrada ao seu momento.',
        image: './frontend/img/service-acupuncture.jpg',
        alt: 'Sessão de acupuntura em um ambiente tranquilo'
    },
    reiki: {
        category: 'Cuidado energético',
        name: 'Reiki',
        description: 'Uma prática de imposição ou aproximação das mãos que convida ao relaxamento, à presença e à percepção do próprio campo energético.',
        note: 'Um momento de pausa e reconexão conduzido em ambiente acolhedor.',
        image: './frontend/img/service-reiki.jpg',
        alt: 'Prática de Reiki realizada com as mãos próximas ao corpo'
    },
    auriculoterapia: {
        category: 'Microssistema auricular',
        name: 'Auriculoterapia',
        description: 'Estimula pontos específicos da orelha relacionados, segundo a abordagem terapêutica, a diferentes regiões e funções do organismo.',
        note: 'Os pontos são escolhidos a partir da anamnese e do cuidado individual.',
        image: './frontend/img/service-auriculotherapy.jpg',
        alt: 'Aplicação de auriculoterapia em pontos específicos da orelha'
    },
    ventosaterapia: {
        category: 'Técnica tradicional',
        name: 'Ventosaterapia',
        description: 'Aplica copos próprios sobre a pele para criar uma sucção controlada, seguindo uma avaliação responsável das regiões trabalhadas.',
        note: 'A intensidade e o tempo de aplicação são definidos para cada atendimento.',
        image: './frontend/img/service-cupping.jpg',
        alt: 'Sessão de ventosaterapia com copos aplicados nas costas'
    },
    shiatsu: {
        category: 'Terapia manual japonesa',
        name: 'Shiatsu',
        description: 'Trabalha pressões rítmicas com os dedos e as mãos ao longo do corpo, respeitando limites, necessidades e resposta de cada pessoa.',
        note: 'Toque consciente e ritmo fazem parte de uma experiência profundamente atenta.',
        image: './frontend/img/service-shiatsu.jpg',
        alt: 'Sessão de Shiatsu com pressão terapêutica nas costas'
    },
    reflexologia: {
        category: 'Terapia por pontos reflexos',
        name: 'Reflexologia',
        description: 'Utiliza pressões em áreas reflexas, especialmente nos pés, dentro de uma proposta de relaxamento e percepção integral do corpo.',
        note: 'A técnica é incorporada ao cuidado conforme a avaliação do atendimento.',
        image: './frontend/img/service-reflexology.jpg',
        alt: 'Sessão de reflexologia com pressão terapêutica nos pés'
    },
    massagens: {
        category: 'Terapias manuais',
        name: 'Massagens terapêuticas',
        description: 'Diferentes modalidades de toque e manobras são selecionadas para criar uma experiência de cuidado, relaxamento e consciência corporal.',
        note: 'Cada sessão considera preferências, objetivos e limites individuais.',
        image: './frontend/img/service-massage.jpg',
        alt: 'Massagem terapêutica realizada por profissional'
    }
};

const serviceSection = document.querySelector('[data-services]');
const serviceOptions = [...document.querySelectorAll('[data-service]')];
const serviceMedia = document.querySelector('.services__media');
const serviceImage = document.querySelector('#service-image');
const serviceCounter = document.querySelector('#service-counter');
const serviceCategory = document.querySelector('#service-category');
const serviceName = document.querySelector('#service-name');
const serviceDescription = document.querySelector('#service-description');
const serviceNote = document.querySelector('#service-note');
let imageTransitionTimer;
let imageTransitionId = 0;

[...new Set(Object.values(serviceData).map(service => service.image))].forEach(source => {
    const image = new Image();
    image.src = source;
});

const activateService = option => {
    const data = serviceData[option.dataset.service];
    const index = serviceOptions.indexOf(option);
    if (!data) return;

    const transitionId = ++imageTransitionId;
    clearTimeout(imageTransitionTimer);
    serviceMedia.classList.remove('is-entering');
    serviceMedia.classList.add('is-leaving');

    imageTransitionTimer = window.setTimeout(() => {
        if (transitionId !== imageTransitionId) return;

        serviceImage.src = data.image;
        serviceImage.alt = data.alt;
        serviceMedia.classList.remove('is-leaving');
        serviceMedia.classList.add('is-entering');

        imageTransitionTimer = window.setTimeout(() => {
            if (transitionId === imageTransitionId) {
                serviceMedia.classList.remove('is-entering');
            }
        }, 520);
    }, 210);

    serviceCounter.textContent = String(index + 1).padStart(2, '0');
    serviceCategory.textContent = data.category;
    serviceName.textContent = data.name;
    serviceDescription.textContent = data.description;
    serviceNote.textContent = data.note;

    serviceOptions.forEach(item => {
        const isActive = item === option;
        item.classList.toggle('is-active', isActive);
        item.setAttribute('aria-selected', isActive);
        item.tabIndex = isActive ? 0 : -1;
    });
};

serviceOptions.forEach((option, index) => {
    option.addEventListener('click', () => activateService(option));
    option.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
        event.preventDefault();
        const direction = ['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1;
        const next = serviceOptions[(index + direction + serviceOptions.length) % serviceOptions.length];
        next.focus();
        activateService(next);
    });
});
