/*
 * Lógica de la web del Centro de Control (simula el comportamiento de Angular).
 * Se carga en login.html y dashboard.html; detecta en qué página está y actúa.
 */

// Expresión regular de caracteres permitidos en el usuario: letras, números, . _ @ -
const USERNAME_PATTERN = /^[A-Za-z0-9._@-]+$/;

// Atajo para buscar un elemento por su data-testid.
function byTestId(id) {
  return document.querySelector(`[data-testid="${id}"]`);
}

// Muestra (o esconde, si el texto está vacío) un mensaje en un elemento.
function showMessage(element, text) {
  element.textContent = text;
  element.hidden = !text;
}

/* ------------------------------ PÁGINA DE LOGIN ------------------------------ */
function initLogin() {
  const form = byTestId('login-form');
  const username = byTestId('login-username');
  const password = byTestId('login-password');
  const submit = byTestId('login-submit');
  const usernameError = byTestId('username-error');
  const passwordError = byTestId('password-error');
  const loginError = byTestId('login-error');

  // Se ejecuta al presionar "Entrar" (o Enter dentro del formulario).
  form.addEventListener('submit', async (event) => {
    // Evita que el navegador recargue la página.
    event.preventDefault();
    // Limpiamos mensajes anteriores.
    showMessage(usernameError, '');
    showMessage(passwordError, '');
    showMessage(loginError, '');

    // Validaciones del lado del cliente.
    const user = username.value.trim();
    let valid = true;
    if (!user) {
      showMessage(usernameError, 'El usuario es obligatorio');
      valid = false;
    } else if (!USERNAME_PATTERN.test(user)) {
      showMessage(usernameError, 'El usuario contiene caracteres no permitidos');
      valid = false;
    }
    if (!password.value) {
      showMessage(passwordError, 'La contraseña es obligatoria');
      valid = false;
    }
    if (!valid) return;

    // Deshabilitamos el botón para evitar doble envío.
    submit.disabled = true;
    try {
      // Llamada real a la API de autenticación.
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: user, password: password.value }),
      });
      if (!response.ok) {
        // Mensaje genérico: no revela si falló el usuario o la contraseña.
        showMessage(loginError, 'Usuario o contraseña incorrectos');
        return;
      }
      const data = await response.json();
      // Guardamos el token y el nombre en sessionStorage (se borra al cerrar la pestaña).
      sessionStorage.setItem('token', data.accessToken);
      sessionStorage.setItem('userName', data.user.name);
      // Navegamos a la landing page.
      window.location.assign('/control/dashboard');
    } catch (error) {
      showMessage(loginError, 'No fue posible conectar con el servidor');
    } finally {
      submit.disabled = false;
    }
  });
}

/* ------------------------------ PÁGINA DASHBOARD ----------------------------- */
async function initDashboard() {
  const token = sessionStorage.getItem('token');
  // Sin sesión no se puede ver el panel: volvemos al login.
  if (!token) {
    window.location.assign('/control/login');
    return;
  }
  byTestId('welcome-message').textContent = `Bienvenido, ${sessionStorage.getItem('userName')}`;
  byTestId('logout-button').addEventListener('click', () => {
    sessionStorage.clear();
    window.location.assign('/control/login');
  });

  // Cargamos los pedidos desde la API con el token.
  const response = await fetch('/api/v1/orders', { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) return;
  const data = await response.json();
  const tbody = byTestId('orders-table').querySelector('tbody');
  for (const order of data.items) {
    const row = document.createElement('tr');
    row.setAttribute('data-testid', `order-row-${order.orderId}`);
    // textContent (y no innerHTML) evita inyectar HTML/JS: protección contra XSS.
    for (const value of [order.orderId, order.warehouseId, order.status, order.operatorId || '-']) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    }
    tbody.appendChild(row);
  }
}

// Punto de entrada: según el formulario o tabla presente, iniciamos la página correcta.
if (byTestId('login-form')) initLogin();
if (byTestId('orders-table')) initDashboard();
