const loginForm = document.querySelector('#login-form');
const panel = document.querySelector('#agenda-panel');
const error = document.querySelector('#form-error');
const dateInput = document.querySelector('#availability-date');
const output = document.querySelector('#availability');

async function request(url, options) {
  const response = await fetch(url, { credentials: 'same-origin', ...options });
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(data?.error || 'Não foi possível concluir a solicitação.');
  return data;
}

loginForm?.addEventListener('submit', async (event) => {
  event.preventDefault(); error.textContent = '';
  const body = Object.fromEntries(new FormData(loginForm));
  try {
    const result = await request('/api/auth/login', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
    if (result.role !== 'patient') throw new Error('Este acesso é exclusivo para pacientes.');
    loginForm.hidden = true; panel.hidden = false; dateInput.valueAsDate = new Date(); dateInput.dispatchEvent(new Event('change'));
  } catch (err) { error.textContent = err.message; }
});

dateInput?.addEventListener('change', async () => {
  try {
    const data = await request(`/api/patient/availability?date=${dateInput.value}`);
    const slots = ['08:00','09:00','10:00','11:00','14:00','15:00','16:00','17:00'];
    output.innerHTML = slots.map(start => `<div class="slot ${data.busy.some(slot => slot.start === start) ? 'busy' : 'free'}">${start} · ${data.busy.some(slot => slot.start === start) ? 'Ocupado' : 'Livre'}</div>`).join('');
  } catch (err) { output.textContent = err.message; }
});
document.querySelector('#logout')?.addEventListener('click', () => request('/api/auth/logout',{method:'POST'}).finally(() => location.reload()));

