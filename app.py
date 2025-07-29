# app.py
import eventlet
eventlet.monkey_patch() 
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from sqlalchemy.exc import IntegrityError
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from sqlalchemy import or_, cast
from functools import wraps
import click
from getpass import getpass
from flask_socketio import SocketIO

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil-de-adivinhar'

# Configuração correta para o SocketIO
socketio = SocketIO(app, async_mode='eventlet')

database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça login para aceder a esta página."
login_manager.login_message_category = "info"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)


class Anexo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    entrada_id = db.Column(db.Integer, db.ForeignKey('entrada.id'), nullable=False)


class Entrada(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    numero_pedido = db.Column(db.Integer, unique=True, nullable=False)
    data_registro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cliente = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Não iniciado')
    descricao = db.Column(db.Text, nullable=False)
    observacoes = db.Column(db.Text, nullable=True)
    arquivado = db.Column(db.Boolean, default=False, nullable=False)
    anexos = db.relationship('Anexo', backref='entrada', lazy=True, cascade="all, delete-orphan")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Acesso negado. Apenas administradores podem aceder a esta página.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def get_dashboard_data():
    pedidos_query = Entrada.query.filter_by(tipo='Pedido', arquivado=False)
    pedidos_dashboard = {
        'total': pedidos_query.count(),
        'nao_iniciado': pedidos_query.filter_by(status='Não iniciado').count(),
        'em_andamento': pedidos_query.filter_by(status='Em andamento').count(),
        'concluido': pedidos_query.filter_by(status='Concluído').count()
    }
    orcamentos_query = Entrada.query.filter_by(tipo='Orçamento', arquivado=False)
    orcamentos_dashboard = {
        'total': orcamentos_query.count(),
        'nao_iniciado': orcamentos_query.filter_by(status='Não iniciado').count(),
        'em_andamento': orcamentos_query.filter_by(status='Em andamento').count(),
        'concluido': orcamentos_query.filter_by(status='Concluído').count()
    }
    return {'pedidos': pedidos_dashboard, 'orcamentos': orcamentos_dashboard}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login sem sucesso. Verifique o utilizador e a senha.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout efetuado com sucesso.', 'success')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    search_query = request.args.get('q', '')
    selected_status = request.args.get('status', '')
    pedidos_base_query = Entrada.query.filter_by(tipo='Pedido', arquivado=False)
    orcamentos_base_query = Entrada.query.filter_by(tipo='Orçamento', arquivado=False)
    if search_query:
        search_term = f"%{search_query}%"
        pedidos_base_query = pedidos_base_query.filter(or_(cast(Entrada.numero_pedido, db.String).ilike(search_term), Entrada.cliente.ilike(search_term), Entrada.descricao.ilike(search_term)))
        orcamentos_base_query = orcamentos_base_query.filter(or_(cast(Entrada.numero_pedido, db.String).ilike(search_term), Entrada.cliente.ilike(search_term), Entrada.descricao.ilike(search_term)))
    if selected_status:
        pedidos_base_query = pedidos_base_query.filter_by(status=selected_status)
        orcamentos_base_query = orcamentos_base_query.filter_by(status=selected_status)
    pedidos = pedidos_base_query.order_by(Entrada.numero_pedido).all()
    orcamentos = orcamentos_base_query.order_by(Entrada.numero_pedido).all()
    dashboard_data = get_dashboard_data()
    return render_template('index.html', dashboard=dashboard_data, pedidos=pedidos, orcamentos=orcamentos, search_query=search_query, selected_status=selected_status)


@app.route('/novo', methods=['GET', 'POST'])
@login_required
def nova_entrada():
    if request.method == 'POST':
        numero_pedido_str = request.form.get('numero_pedido')
        if not numero_pedido_str.isdigit():
            flash('O N° de entrada deve conter apenas números.', 'danger')
            return render_template('nova_entrada.html', form_data=request.form)
        numero_pedido = int(numero_pedido_str)
        if Entrada.query.filter_by(numero_pedido=numero_pedido).first():
            flash(f'O N° de entrada {numero_pedido} já existe. Tente outro.', 'danger')
            return render_template('nova_entrada.html', form_data=request.form)
        nova_entrada_obj = Entrada(tipo=request.form.get('tipo'), numero_pedido=numero_pedido, cliente=request.form.get('cliente'), status=request.form.get('status'), descricao=request.form.get('descricao'), observacoes=request.form.get('observacoes'))
        db.session.add(nova_entrada_obj)
        uploaded_files = request.files.getlist('anexos')
        for ficheiro in uploaded_files:
            if ficheiro and ficheiro.filename != '':
                anexo_filename = secure_filename(ficheiro.filename)
                ficheiro.save(os.path.join(app.config['UPLOAD_FOLDER'], anexo_filename))
                novo_anexo = Anexo(filename=anexo_filename, entrada=nova_entrada_obj)
                db.session.add(novo_anexo)
        db.session.commit()
        socketio.emit('update_data')
        flash(f"{nova_entrada_obj.tipo} criado com sucesso!", 'success')
        return redirect(url_for('index'))
    return render_template('nova_entrada.html', form_data={})


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_entrada(id):
    entrada = Entrada.query.get_or_404(id)
    if request.method == 'POST':
        entrada.tipo = request.form.get('tipo')
        entrada.numero_pedido = int(request.form.get('numero_pedido'))
        entrada.cliente = request.form.get('cliente')
        entrada.status = request.form.get('status')
        entrada.descricao = request.form.get('descricao')
        entrada.observacoes = request.form.get('observacoes')
        uploaded_files = request.files.getlist('anexos')
        for ficheiro in uploaded_files:
            if ficheiro and ficheiro.filename != '':
                anexo_filename = secure_filename(ficheiro.filename)
                ficheiro.save(os.path.join(app.config['UPLOAD_FOLDER'], anexo_filename))
                novo_anexo = Anexo(filename=anexo_filename, entrada=entrada)
                db.session.add(novo_anexo)
        db.session.commit()
        socketio.emit('update_data')
        flash(f'{entrada.tipo} atualizado com sucesso!', 'success')
        return redirect(url_for('editar_entrada', id=id))
    return render_template('editar_entrada.html', entrada=entrada)


@app.route('/excluir-anexo/<int:anexo_id>', methods=['POST'])
@login_required
def excluir_anexo(anexo_id):
    anexo = Anexo.query.get_or_404(anexo_id)
    entrada_id = anexo.entrada_id
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], anexo.filename))
    except FileNotFoundError:
        pass
    db.session.delete(anexo)
    db.session.commit()
    socketio.emit('update_data')
    flash('Anexo excluído com sucesso.', 'success')
    return redirect(url_for('editar_entrada', id=entrada_id))


@app.route('/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_entrada(id):
    entrada_a_excluir = Entrada.query.get_or_404(id)
    for anexo in entrada_a_excluir.anexos:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], anexo.filename))
        except FileNotFoundError:
            pass
    db.session.delete(entrada_a_excluir)
    db.session.commit()
    socketio.emit('update_data')
    tipo_entrada = entrada_a_excluir.tipo
    if entrada_a_excluir.arquivado:
        flash(f'{tipo_entrada} arquivado foi excluído permanentemente!', 'danger')
        return redirect(url_for('pedidos_arquivados'))
    flash(f'{tipo_entrada} foi excluído com sucesso!', 'danger')
    return redirect(url_for('index'))


@app.route('/atualizar-status/<int:id>', methods=['POST'])
@login_required
def atualizar_status(id):
    entrada = Entrada.query.get_or_404(id)
    data = request.get_json()
    novo_status = data.get('status')
    if novo_status in ['Não iniciado', 'Em andamento', 'Concluído']:
        entrada.status = novo_status
        db.session.commit()
        socketio.emit('update_data')
        novos_dados_dashboard = get_dashboard_data()
        return jsonify({'success': True, 'message': 'Status atualizado com sucesso!', 'dashboard': novos_dados_dashboard})
    return jsonify({'success': False, 'message': 'Status inválido.'}), 400


@app.route('/converter/<int:id>', methods=['POST'])
@login_required
def converter_para_pedido(id):
    orcamento = Entrada.query.get_or_404(id)
    if orcamento.tipo == 'Orçamento':
        orcamento.tipo = 'Pedido'
        orcamento.status = 'Não iniciado'
        db.session.commit()
        socketio.emit('update_data')
        flash(f"Orçamento #{orcamento.numero_pedido} foi convertido em Pedido com sucesso!", 'success')
    else:
        flash('Esta entrada já é um Pedido.', 'warning')
    return redirect(url_for('index'))


@app.route('/arquivar/<int:id>', methods=['POST'])
@login_required
def arquivar_entrada(id):
    entrada = Entrada.query.get_or_404(id)
    entrada.arquivado = True
    db.session.commit()
    socketio.emit('update_data')
    flash(f'{entrada.tipo} #{entrada.numero_pedido} foi arquivado com sucesso.', 'success')
    return redirect(url_for('index'))


@app.route('/desarquivar/<int:id>', methods=['POST'])
@login_required
def desarquivar_entrada(id):
    entrada = Entrada.query.get_or_404(id)
    entrada.arquivado = False
    db.session.commit()
    socketio.emit('update_data')
    flash(f'{entrada.tipo} #{entrada.numero_pedido} foi restaurado com sucesso.', 'success')
    return redirect(url_for('pedidos_arquivados'))


@app.route('/arquivados')
@login_required
def pedidos_arquivados():
    # Lógica de filtro (mantida para futura implementação na página de arquivados)
    search_query = request.args.get('q', '')
    selected_status = request.args.get('status', '')

    # Busca pedidos arquivados
    pedidos_arquivados_query = Entrada.query.filter_by(tipo='Pedido', arquivado=True)
    # Busca orçamentos arquivados
    orcamentos_arquivados_query = Entrada.query.filter_by(tipo='Orçamento', arquivado=True)

    # (A lógica de filtro pode ser aplicada aqui no futuro, se necessário)

    pedidos = pedidos_arquivados_query.order_by(Entrada.data_registro.desc()).all()
    orcamentos = orcamentos_arquivados_query.order_by(Entrada.data_registro.desc()).all()

    return render_template('pedidos_arquivados.html', pedidos=pedidos, orcamentos=orcamentos, 
                           search_query=search_query, selected_status=selected_status)


@app.route('/gerir_usuarios', methods=['GET', 'POST'])
@login_required
@admin_required
def gerir_usuarios():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        is_admin = 'is_admin' in request.form
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Este nome de utilizador já existe.', 'danger')
        else:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(username=username, password_hash=hashed_password, is_admin=is_admin)
            db.session.add(new_user)
            db.session.commit()
            socketio.emit('update_data')
            flash(f'Utilizador {username} criado com sucesso!', 'success')
        return redirect(url_for('gerir_usuarios'))
    users = User.query.all()
    return render_template('gerir_usuarios.html', users=users)


@app.route('/excluir_usuario/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def excluir_usuario(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.id == current_user.id:
        flash('Não pode excluir a sua própria conta de administrador.', 'danger')
        return redirect(url_for('gerir_usuarios'))
    db.session.delete(user_to_delete)
    db.session.commit()
    socketio.emit('update_data')
    flash(f'Utilizador {user_to_delete.username} excluído com sucesso.', 'success')
    return redirect(url_for('gerir_usuarios'))
    

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    response = send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Base de dados inicializada e tabelas criadas.")


@app.cli.command("create-admin")
def create_admin_command():
    username = input("Digite o nome de utilizador do ADMIN: ")
    password = getpass("Digite a senha do ADMIN: ")
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        print(f"Erro: O utilizador '{username}' já existe.")
        return
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password_hash=hashed_password, is_admin=True)
    db.session.add(new_user)
    db.session.commit()
    print(f"Utilizador ADMINISTRADOR '{username}' criado com sucesso!")


if __name__ == '__main__':
    app.run()