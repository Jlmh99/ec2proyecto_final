const CLAVE_TOKEN = "token";
const CLAVE_USUARIO = "usuario";

function obtenerToken() { return localStorage.getItem(CLAVE_TOKEN); }
function obtenerUsuario() {
  try { return JSON.parse(localStorage.getItem(CLAVE_USUARIO)); } catch (e) { return null; }
}
function guardarSesion(token, usuario) {
  localStorage.setItem(CLAVE_TOKEN, token);
  localStorage.setItem(CLAVE_USUARIO, JSON.stringify(usuario));
}
function cerrarSesion() {
  localStorage.removeItem(CLAVE_TOKEN);
  localStorage.removeItem(CLAVE_USUARIO);
  window.location.href = "/login";
}

async function peticion(url, metodo, cuerpo) {
  const cabeceras = { "Content-Type": "application/json" };
  const token = obtenerToken();
  if (token) cabeceras["Authorization"] = "Bearer " + token;
  const resp = await fetch(url, { method: metodo, headers: cabeceras, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
  let json = {};
  try { json = await resp.json(); } catch (e) { json = { data: { error: "Respuesta no válida del servidor" } }; }
  return { ok: resp.ok, status: resp.status, cuerpo: json };
}

function mostrarMensaje(texto, esError) {
  const caja = document.getElementById("mensaje");
  if (!caja) return;
  caja.textContent = texto;
  caja.className = "mensaje " + (esError ? "error" : "ok");
}

function dibujarNavegacion() {
  const nav = document.getElementById("nav");
  if (!nav) return;
  if (obtenerToken()) {
    const salir = document.createElement("button");
    salir.id = "btn-salir";
    salir.textContent = "Cerrar sesión";
    salir.className = "secundario";
    salir.addEventListener("click", cerrarSesion);
    nav.appendChild(salir);
  }
}
document.addEventListener("DOMContentLoaded", dibujarNavegacion);
