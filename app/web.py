from flask import Blueprint, redirect, render_template, url_for

web = Blueprint("web", __name__)


@web.get("/")
def inicio():
    return redirect(url_for("web.login"))


@web.get("/login")
def login():
    return render_template("login.html")


@web.get("/register")
def register():
    return render_template("register.html")


@web.get("/usuarios")
def usuarios():
    return render_template("usuarios.html")
