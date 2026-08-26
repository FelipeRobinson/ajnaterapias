const form = document.querySelector('#crm-login');
const error = document.querySelector('#form-error');

async function request(url, options) {
  const response = await fetch(url, { credentials:'same-origin', ...options });
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(data?.error || 'Acesso não autorizado.');
  return data;
}

form?.addEventListener('submit', async event => {
  event.preventDefault(); error.textContent = '';
  try {
    const result = await request('/api/auth/login', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Object.fromEntries(new FormData(form))) });
    if (result.role !== 'admin') throw new Error('Este acesso exige perfil de administrador.');
    location.assign('/crm/painel');
  } catch (err) { error.textContent = err.message; }
});

async function loadDashboard() {
  if (!document.querySelector('.dashboard')) return;
  try {
    const [dashboard, patients] = await Promise.all([request('/api/admin/dashboard'), request('/api/admin/patients')]);
    document.querySelector('#patient-count').textContent = dashboard.patients;
    document.querySelector('#appointment-count').textContent = dashboard.appointments_today;
    document.querySelector('#patients').innerHTML = patients.items.map(patient => `<div class="patient-row"><strong>${patient.name}</strong><span>${patient.phone || patient.email || 'Sem contato'}</span></div>`).join('') || '<p>Nenhum paciente cadastrado.</p>';
  } catch (_) { location.assign('/crm'); }
}
document.querySelector('#logout')?.addEventListener('click', () => request('/api/auth/logout',{method:'POST'}).finally(() => location.assign('/crm')));
loadDashboard();
