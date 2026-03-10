from flask import Flask, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from flask_mail import Mail, Message
import webbrowser

app = Flask(__name__)
app.secret_key = "polloselrey2025"

# -------------------------------------------------------------
# 🔗 CONEXIÓN A MONGODB
# -------------------------------------------------------------
try:
    cliente = MongoClient("mongodb://localhost:27017/")
    db = cliente["pollos_el_rey"]
    print("✅ Conectado correctamente a MongoDB")
except Exception as e:
    print("❌ Error al conectar con MongoDB:", e)

# Colecciones
productos_col = db["productos"]
pedidos_col = db["pedidos"]
usuarios_col = db["usuarios_admin"]
logs_col = db["logs"]
mensajes_col = db["mensajes"]

# -------------------------------------------------------------
# 📧 CONFIGURACIÓN DE CORREO (usa una contraseña de aplicación)
# -------------------------------------------------------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'leoneldiaz8620@gmail.com'  # ✅ tu correo
app.config['MAIL_PASSWORD'] = 'mzrfkkorwdjldicj'           # ✅ contraseña de aplicación
app.config['MAIL_DEFAULT_SENDER'] = ('Pollos El Rey', 'leoneldiaz8620@gmail.com')
app.config['MAIL_DEBUG'] = True  # 🔍 Activa logs de depuración SMTP

mail = Mail(app)

# -------------------------------------------------------------
# 🧾 FUNCIÓN GLOBAL PARA REGISTRAR LOGS
# -------------------------------------------------------------
def registrar_log(accion, coleccion, datos):
    """Guarda una acción realizada en la colección logs"""
    logs_col.insert_one({
        "accion": accion,
        "coleccion": coleccion,
        "datos": datos,
        "usuario": session.get("usuario_admin", "cliente"),
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    })

# -------------------------------------------------------------
# 🌐 PÁGINAS PRINCIPALES
# -------------------------------------------------------------
@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/promociones')
def promociones():
    return render_template('promociones.html')

@app.route('/nosotros')
def nosotros():
    return render_template('nosotros.html')

# -------------------------------------------------------------
# 📧 CONTACTO (envía correo + guarda en MongoDB)
# -------------------------------------------------------------
@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        correo = request.form.get('correo')
        asunto = request.form.get('asunto')
        mensaje = request.form.get('mensaje')

        if not correo or not asunto or not mensaje:
            flash("⚠️ Debes llenar todos los campos antes de enviar.", "warning")
            return redirect(url_for('contacto'))

        try:
            # --- 📤 Enviar correo al administrador ---
            msg = Message(
                subject=f"📩 Nuevo mensaje: {asunto}",
                recipients=['leoneldiaz8620@gmail.com'],  # ✅ tu correo destino
                body=f"De: {correo}\n\nMensaje:\n{mensaje}"
            )
            mail.send(msg)

            # --- 💾 Guardar en MongoDB ---
            mensajes_col.insert_one({
                "correo": correo,
                "asunto": asunto,
                "mensaje": mensaje,
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            })

            registrar_log("Nuevo mensaje de contacto", "mensajes", {"correo": correo, "asunto": asunto})
            flash("✅ Tu mensaje fue enviado correctamente. ¡Gracias por contactarnos!", "success")

        except Exception as e:
            print("❌ Error al enviar correo:", e)
            flash("❌ Ocurrió un error al enviar el mensaje. Intenta más tarde.", "danger")

        return redirect(url_for('contacto'))

    return render_template('contacto.html')

# -------------------------------------------------------------
# 🛒 SISTEMA DE PEDIDOS (CLIENTES)
# -------------------------------------------------------------
@app.route("/ordenar", methods=["POST"])
def ordenar():
    nombre = request.form.get("nombre")
    telefono = request.form.get("telefono")
    producto = request.form.get("producto")
    precio = request.form.get("precio")
    imagen = request.form.get("imagen")

    if not nombre or not telefono:
        flash("⚠️ Debes ingresar tu nombre y teléfono para ordenar.", "warning")
        return redirect(url_for("menu"))

    pedido = {
        "cliente": nombre.strip().title(),
        "telefono": telefono.strip(),
        "producto": producto,
        "precio": float(precio),
        "imagen": imagen,
        "estado": "Pendiente",
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "comentario": ""
    }

    pedidos_col.insert_one(pedido)
    registrar_log("Nuevo pedido", "pedidos", pedido)

    flash("✅ Pedido realizado correctamente.", "success")
    return redirect(url_for("mis_pedidos", telefono=telefono))

@app.route("/mis_pedidos")
def mis_pedidos():
    telefono = request.args.get("telefono")
    pedidos = list(pedidos_col.find({"telefono": telefono})) if telefono else []
    return render_template("mis_pedidos.html", pedidos=pedidos, telefono=telefono or "")

# -------------------------------------------------------------
# 📝 GUARDAR COMENTARIO DE PEDIDO
# -------------------------------------------------------------
@app.route("/guardar_comentario/<id>", methods=["POST"])
def guardar_comentario(id):
    comentario = request.form.get("comentario", "").strip()
    if not comentario:
        return "⚠️ No se recibió comentario", 400

    try:
        pedidos_col.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"comentario": comentario}}
        )
        registrar_log("Comentario agregado", "pedidos", {"_id": id, "comentario": comentario})
        return "✅ Comentario guardado correctamente", 200
    except Exception as e:
        print("❌ Error al guardar comentario:", e)
        return "❌ Error al guardar comentario", 500

# -------------------------------------------------------------
# 🧩 CRUD DE PRODUCTOS (ADMIN)
# -------------------------------------------------------------
@app.route('/productos')
def productos():
    lista = []
    for p in productos_col.find():
        if not all(k in p for k in ["nombre", "categoria", "precio", "stock"]):
            continue
        p['_id'] = str(p['_id'])
        lista.append(p)
    return render_template('productos.html', productos=lista)

@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        categoria = request.form['categoria'].strip()
        precio = float(request.form['precio'])
        stock = int(request.form['stock'])
        nuevo_producto = {
            "nombre": nombre,
            "categoria": categoria,
            "precio": precio,
            "stock": stock
        }
        productos_col.insert_one(nuevo_producto)
        registrar_log("Producto agregado", "productos", nuevo_producto)
        flash("✅ Producto agregado correctamente", "success")
        return redirect(url_for('productos'))
    return render_template('agregar.html')

@app.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    producto = productos_col.find_one({"_id": ObjectId(id)})
    if not producto:
        flash("❌ Producto no encontrado", "danger")
        return redirect(url_for('productos'))

    if request.method == 'POST':
        datos_actualizados = {
            "nombre": request.form['nombre'].strip(),
            "categoria": request.form['categoria'].strip(),
            "precio": float(request.form['precio']),
            "stock": int(request.form['stock'])
        }
        productos_col.update_one({"_id": ObjectId(id)}, {"$set": datos_actualizados})
        registrar_log("Producto actualizado", "productos", datos_actualizados)
        flash("✏️ Producto actualizado correctamente", "info")
        return redirect(url_for('productos'))

    return render_template('editar.html', producto=producto)

@app.route('/eliminar/<id>')
def eliminar(id):
    productos_col.delete_one({"_id": ObjectId(id)})
    registrar_log("Producto eliminado", "productos", {"_id": id})
    flash("🗑️ Producto eliminado con éxito", "danger")
    return redirect(url_for('productos'))

# -------------------------------------------------------------
# 🔐 LOGIN ADMINISTRADOR
# -------------------------------------------------------------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        clave = request.form.get("clave")

        admin = usuarios_col.find_one({"usuario": usuario})

        if admin:
            if admin["clave"] == clave:
                session["admin_autenticado"] = True
                session["usuario_admin"] = usuario
                registrar_log("Login admin", "usuarios_admin", {"usuario": usuario})
                flash("✅ Sesión iniciada correctamente.", "success")
                return redirect(url_for("admin_ordenes"))
            else:
                flash("❌ Usuario o contraseña incorrectos.", "danger")
                return redirect(url_for("admin_login"))
        else:
            usuarios_col.insert_one({
                "usuario": usuario,
                "clave": clave,
                "rol": "admin"
            })
            session["admin_autenticado"] = True
            session["usuario_admin"] = usuario
            registrar_log("Nuevo admin creado", "usuarios_admin", {"usuario": usuario})
            flash("🆕 Usuario registrado y sesión iniciada correctamente.", "success")
            return redirect(url_for("admin_ordenes"))

    return render_template("admin_login.html")
# -------------------------------------------------------------
# 👥 PANEL DE USUARIOS ADMIN Y EMPLEADOS
# -------------------------------------------------------------
@app.route("/admin_usuarios")
def admin_usuarios():
    if not session.get("admin_autenticado"):
        flash("⚠️ Inicia sesión para acceder al panel de usuarios.", "warning")
        return redirect(url_for("admin_login"))

    usuarios = list(usuarios_col.find())
    for u in usuarios:
        u["_id"] = str(u["_id"])
    return render_template("admin_usuarios.html", usuarios=usuarios)


# -------------------------------------------------------------
# ➕ AGREGAR NUEVO USUARIO
# -------------------------------------------------------------
@app.route("/agregar_usuario", methods=["POST"])
def agregar_usuario():
    if not session.get("admin_autenticado"):
        return redirect(url_for("admin_login"))

    usuario = request.form.get("usuario").strip()
    clave = request.form.get("clave").strip()
    rol = request.form.get("rol")

    if usuarios_col.find_one({"usuario": usuario}):
        flash("⚠️ Ya existe un usuario con ese nombre.", "warning")
        return redirect(url_for("admin_usuarios"))

    nuevo = {"usuario": usuario, "clave": clave, "rol": rol}
    usuarios_col.insert_one(nuevo)
    registrar_log("Nuevo usuario creado", "usuarios_admin", nuevo)
    flash("✅ Usuario agregado correctamente.", "success")
    return redirect(url_for("admin_usuarios"))


# -------------------------------------------------------------
# 🔄 ACTUALIZAR CONTRASEÑA
# -------------------------------------------------------------
@app.route("/actualizar_clave/<id>", methods=["POST"])
def actualizar_clave(id):
    if not session.get("admin_autenticado"):
        return redirect(url_for("admin_login"))

    nueva_clave = request.form.get("nueva_clave").strip()
    usuarios_col.update_one({"_id": ObjectId(id)}, {"$set": {"clave": nueva_clave}})
    registrar_log("Contraseña actualizada", "usuarios_admin", {"_id": id})
    flash("🔑 Contraseña actualizada correctamente.", "info")
    return redirect(url_for("admin_usuarios"))


# -------------------------------------------------------------
# 🗑️ ELIMINAR USUARIO
# -------------------------------------------------------------
@app.route("/eliminar_usuario/<id>")
def eliminar_usuario(id):
    if not session.get("admin_autenticado"):
        return redirect(url_for("admin_login"))

    usuario = usuarios_col.find_one({"_id": ObjectId(id)})
    if usuario and usuario["rol"] != "admin":
        usuarios_col.delete_one({"_id": ObjectId(id)})
        registrar_log("Usuario eliminado", "usuarios_admin", {"usuario": usuario["usuario"]})
        flash("🗑️ Usuario eliminado correctamente.", "danger")
    else:
        flash("⚠️ No puedes eliminar un administrador.", "warning")

    return redirect(url_for("admin_usuarios"))


# -------------------------------------------------------------
# 📋 PANEL DE ÓRDENES ADMIN
# -------------------------------------------------------------
@app.route("/admin_ordenes")
def admin_ordenes():
    if not session.get("admin_autenticado"):
        flash("⚠️ Inicia sesión para acceder al panel.", "warning")
        return redirect(url_for("admin_login"))
    pedidos = list(pedidos_col.find())
    return render_template("admin_ordenes.html", pedidos=pedidos)

# -------------------------------------------------------------
# 🧾 PANEL DE LOGS
# -------------------------------------------------------------
@app.route("/admin_logs")
def admin_logs():
    if not session.get("admin_autenticado"):
        flash("⚠️ Inicia sesión para acceder al panel de logs.", "warning")
        return redirect(url_for("admin_login"))

    logs = list(db["logs"].find().sort("fecha", -1))
    for log in logs:
        if "_id" in log:
            log["_id"] = str(log["_id"])
        if "datos" in log and isinstance(log["datos"], dict):
            for key, value in log["datos"].items():
                if isinstance(value, ObjectId):
                    log["datos"][key] = str(value)
    return render_template("admin_logs.html", logs=logs)


# -------------------------------------------------------------
# 🗑️ ELIMINAR LOG
# -------------------------------------------------------------
@app.route("/admin/logs/eliminar/<id>", methods=["POST"])
def eliminar_log(id):
    logs_collection.delete_one({"_id": ObjectId(id)})
    flash("Registro eliminado correctamente", "success")
    return redirect(url_for("logs"))


@app.route("/eliminar_todos_los_logs", methods=["POST"])
def eliminar_todos_los_logs():
    if not session.get("admin_autenticado"):
        flash("⚠️ Debes iniciar sesión.", "warning")
        return redirect(url_for("admin_login"))

    try:
        logs_col.delete_many({})
        flash("🗑️ Todos los logs fueron eliminados correctamente.", "success")
    except:
        flash("❌ No se pudieron eliminar los logs.", "danger")

    return redirect(url_for("admin_logs"))

# -------------------------------------------------------------
# 🔄 CAMBIAR ESTADO DE PEDIDO
# -------------------------------------------------------------
@app.route("/cambiar_estado/<id>", methods=["POST"])
def cambiar_estado(id):
    if not session.get("admin_autenticado"):
        return redirect(url_for("admin_login"))
    nuevo_estado = request.form.get("estado")
    pedidos_col.update_one({"_id": ObjectId(id)}, {"$set": {"estado": nuevo_estado}})
    registrar_log("Cambio de estado de pedido", "pedidos", {"_id": id, "estado": nuevo_estado})
    flash("🔄 Estado del pedido actualizado.", "info")
    return redirect(url_for("admin_ordenes"))

# -------------------------------------------------------------
# 🗑️ ELIMINAR PEDIDO
# -------------------------------------------------------------
@app.route("/eliminar_pedido/<id>", methods=["POST"])
def eliminar_pedido(id):
    if not session.get("admin_autenticado"):
        return redirect(url_for("admin_login"))
    pedidos_col.delete_one({"_id": ObjectId(id)})
    registrar_log("Pedido eliminado", "pedidos", {"_id": id})
    flash("🗑️ Pedido eliminado correctamente.", "danger")
    return redirect(url_for("admin_ordenes"))

# -------------------------------------------------------------
# 🚪 CERRAR SESIÓN
# -------------------------------------------------------------
@app.route("/admin_logout")
def admin_logout():
    usuario = session.get("usuario_admin", "Desconocido")
    registrar_log("Logout admin", "usuarios_admin", {"usuario": usuario})
    session.clear()
    flash("👋 Sesión cerrada correctamente.", "success")
    return redirect(url_for("admin_login"))

# -------------------------------------------------------------
# 🚀 EJECUCIÓN
# -------------------------------------------------------------
if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:5000/admin_login")
    app.run(debug=True)