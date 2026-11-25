"""Pruebas de frontend (Playwright): registro, login, CRUD de usuarios desde la interfaz."""
import re

from playwright.sync_api import Page, expect


# ------------------------------------------------------------------ navegación
def test_raiz_redirige_al_login(page: Page, base_url):
    page.goto(base_url + "/")
    expect(page).to_have_url(re.compile(r"/login$"))
    expect(page.locator("#titulo")).to_have_text("Iniciar sesión")


def test_login_enlace_a_registro(page: Page, base_url):
    page.goto(base_url + "/login")
    page.click("#enlace-registro")
    expect(page).to_have_url(re.compile(r"/register$"))


def test_registro_enlace_a_login(page: Page, base_url):
    page.goto(base_url + "/register")
    page.click("#enlace-login")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_usuarios_sin_sesion_redirige_al_login(page: Page, base_url):
    page.goto(base_url + "/usuarios")
    expect(page).to_have_url(re.compile(r"/login$"))


# ------------------------------------------------------------------ registro
def test_registro_exitoso(page: Page, base_url, datos):
    page.goto(base_url + "/register")
    page.fill("#nombre", datos["nombre"])
    page.fill("#email", datos["email"])
    page.fill("#password", datos["password"])
    page.click("#btn-registro")
    expect(page.locator("#mensaje")).to_contain_text("Cuenta creada correctamente")


def test_registro_correo_duplicado(page: Page, base_url, sesion):
    page.goto(base_url + "/register")
    page.fill("#nombre", "Otro")
    page.fill("#email", sesion["email"])
    page.fill("#password", "Segura12345")
    page.click("#btn-registro")
    expect(page.locator("#mensaje")).to_contain_text("ya esta registrado")


def test_registro_password_corta(page: Page, base_url, datos):
    page.goto(base_url + "/register")
    page.fill("#nombre", datos["nombre"])
    page.fill("#email", datos["email"])
    page.fill("#password", "corta")
    page.click("#btn-registro")
    expect(page.locator("#mensaje")).to_contain_text("al menos 8 caracteres")


def test_registro_correo_invalido(page: Page, base_url, datos):
    page.goto(base_url + "/register")
    page.fill("#nombre", datos["nombre"])
    page.fill("#email", "sin-formato")
    page.fill("#password", datos["password"])
    page.click("#btn-registro")
    expect(page.locator("#mensaje")).to_contain_text("correo no es valido")


def test_registro_nombre_vacio(page: Page, base_url, datos):
    page.goto(base_url + "/register")
    page.fill("#email", datos["email"])
    page.fill("#password", datos["password"])
    page.click("#btn-registro")
    expect(page.locator("#mensaje")).to_contain_text("nombre es obligatorio")


# ------------------------------------------------------------------ login
def test_login_exitoso_lleva_a_usuarios(page: Page, base_url, sesion):
    page.goto(base_url + "/login")
    page.fill("#email", sesion["email"])
    page.fill("#password", sesion["password"])
    page.click("#btn-login")
    expect(page).to_have_url(re.compile(r"/usuarios$"))
    expect(page.locator("#sesion")).to_contain_text(sesion["email"])


def test_login_password_incorrecta(page: Page, base_url, sesion):
    page.goto(base_url + "/login")
    page.fill("#email", sesion["email"])
    page.fill("#password", "incorrecta123")
    page.click("#btn-login")
    expect(page.locator("#mensaje")).to_have_text("Credenciales invalidas")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_login_usuario_inexistente(page: Page, base_url):
    page.goto(base_url + "/login")
    page.fill("#email", "nadie@example.com")
    page.fill("#password", "Segura12345")
    page.click("#btn-login")
    expect(page.locator("#mensaje")).to_have_text("Credenciales invalidas")


def test_login_campos_vacios(page: Page, base_url):
    page.goto(base_url + "/login")
    page.click("#btn-login")
    expect(page.locator("#mensaje")).to_have_text("Credenciales invalidas")


def test_cerrar_sesion(pagina_con_sesion: Page):
    pagina_con_sesion.click("#btn-salir")
    expect(pagina_con_sesion).to_have_url(re.compile(r"/login$"))
    pagina_con_sesion.goto(pagina_con_sesion.url.replace("/login", "/usuarios"))
    expect(pagina_con_sesion).to_have_url(re.compile(r"/login$"))


# ------------------------------------------------------------------ CRUD desde la interfaz
def test_tabla_muestra_al_usuario_en_sesion(pagina_con_sesion: Page, sesion):
    expect(pagina_con_sesion.locator("#tabla-usuarios tbody tr", has_text=sesion["email"])).to_have_count(1)


def test_crear_usuario_desde_la_interfaz(pagina_con_sesion: Page, datos):
    nuevo = {"nombre": "Creado UI", "email": "creado." + datos["email"], "password": "Segura12345"}
    pagina_con_sesion.fill("#u-nombre", nuevo["nombre"])
    pagina_con_sesion.fill("#u-email", nuevo["email"])
    pagina_con_sesion.fill("#u-password", nuevo["password"])
    pagina_con_sesion.click("#btn-guardar")
    expect(pagina_con_sesion.locator("#mensaje")).to_have_text("Usuario creado")
    expect(pagina_con_sesion.locator("#tabla-usuarios tbody tr", has_text=nuevo["email"])).to_have_count(1)


def test_crear_usuario_duplicado_muestra_error(pagina_con_sesion: Page, sesion):
    pagina_con_sesion.fill("#u-nombre", "Repetido")
    pagina_con_sesion.fill("#u-email", sesion["email"])
    pagina_con_sesion.fill("#u-password", "Segura12345")
    pagina_con_sesion.click("#btn-guardar")
    expect(pagina_con_sesion.locator("#mensaje")).to_contain_text("ya esta registrado")


def test_editar_nombre_de_usuario(pagina_con_sesion: Page, api, sesion, datos):
    otro = {"nombre": "Para Editar", "email": "edit." + datos["email"], "password": "Segura12345"}
    api.post("/api/usuarios", data=otro, headers=sesion["headers"])
    pagina_con_sesion.reload()
    fila = pagina_con_sesion.locator("#tabla-usuarios tbody tr", has_text=otro["email"])
    fila.locator(".btn-editar").click()
    expect(pagina_con_sesion.locator("#titulo-form")).to_have_text("Editar usuario")
    pagina_con_sesion.fill("#u-nombre", "Nombre Cambiado")
    pagina_con_sesion.click("#btn-guardar")
    expect(pagina_con_sesion.locator("#mensaje")).to_have_text("Usuario actualizado")
    expect(pagina_con_sesion.locator("#tabla-usuarios tbody tr", has_text="Nombre Cambiado")).to_have_count(1)


def test_cancelar_edicion_limpia_el_formulario(pagina_con_sesion: Page, sesion):
    fila = pagina_con_sesion.locator("#tabla-usuarios tbody tr", has_text=sesion["email"])
    fila.locator(".btn-editar").click()
    pagina_con_sesion.click("#btn-cancelar")
    expect(pagina_con_sesion.locator("#u-nombre")).to_have_value("")
    expect(pagina_con_sesion.locator("#titulo-form")).to_have_text("Nuevo usuario")


def test_eliminar_usuario_desde_la_interfaz(pagina_con_sesion: Page, api, sesion, datos):
    otro = {"nombre": "Para Borrar", "email": "borrar." + datos["email"], "password": "Segura12345"}
    api.post("/api/usuarios", data=otro, headers=sesion["headers"])
    pagina_con_sesion.reload()
    fila = pagina_con_sesion.locator("#tabla-usuarios tbody tr", has_text=otro["email"])
    fila.locator(".btn-eliminar").click()
    expect(pagina_con_sesion.locator("#mensaje")).to_have_text("Usuario eliminado")
    expect(pagina_con_sesion.locator("#tabla-usuarios tbody tr", has_text=otro["email"])).to_have_count(0)


def test_no_se_puede_eliminar_la_cuenta_en_sesion(pagina_con_sesion: Page, sesion):
    fila = pagina_con_sesion.locator("#tabla-usuarios tbody tr", has_text=sesion["email"])
    fila.locator(".btn-eliminar").click()
    expect(pagina_con_sesion.locator("#mensaje")).to_contain_text("No puedes eliminar tu propia cuenta")
