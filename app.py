# app.py
import eventlet # type: ignore
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
from flask_socketio import SocketIO # type: ignore
import fitz # type: ignore # PyMuPDF
import re # Biblioteca para expressões regulares (procurar padrões de texto)

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
            return redirect(url_for('inicio'))
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
        return redirect(url_for('inicio'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('inicio'))
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
def inicio():
    """Renderiza a nova página de início."""
    return render_template('inicio.html')

@app.route('/painel')
@login_required
def painel_controle():
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
    return render_template('painel_controle.html', dashboard=dashboard_data, pedidos=pedidos, orcamentos=orcamentos, search_query=search_query, selected_status=selected_status)

@app.route('/novo', methods=['GET', 'POST'])
@login_required
def nova_entrada():
    if request.method == 'POST':
        tipo_entrada = request.form.get('tipo')
        numero_pedido_str = request.form.get('numero_pedido')

        # Se for um Pedido, o número continua a ser obrigatório
        if tipo_entrada == 'Pedido' and not numero_pedido_str:
            flash('O N° da Entrada é obrigatório para Pedidos.', 'danger')
            return render_template('nova_entrada.html', form_data=request.form)

        # Se for um Orçamento e o campo estiver vazio, geramos um número
        if tipo_entrada == 'Orçamento' and not numero_pedido_str:
            # Usamos o timestamp para garantir um número único
            numero_pedido = int(datetime.now().timestamp())
        else:
            # Se o número foi preenchido, validamos como antes
            if not numero_pedido_str.isdigit():
                flash('O N° de entrada deve conter apenas números.', 'danger')
                return render_template('nova_entrada.html', form_data=request.form)
            numero_pedido = int(numero_pedido_str)

        # Verifica se o número (seja o digitado ou o gerado) já existe
        if Entrada.query.filter_by(numero_pedido=numero_pedido).first():
            flash(f'O N° de entrada {numero_pedido} já existe. Tente outro.', 'danger')
            return render_template('nova_entrada.html', form_data=request.form)

        nova_entrada_obj = Entrada(
            tipo=tipo_entrada,
            numero_pedido=numero_pedido,
            cliente=request.form.get('cliente'),
            status=request.form.get('status'),
            descricao=request.form.get('descricao'),
            observacoes=request.form.get('observacoes')
        )

        # ... (o resto da função para salvar anexos e emitir o sinal continua igual)

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
        return redirect(url_for('painel_controle'))

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
        return redirect(url_for('painel_controle'))
    return render_template('editar_entrada.html', entrada=entrada)

@app.route('/excluir-anexo/<int:anexo_id>', methods=['GET', 'POST'])
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
    return redirect(url_for('inicio'))

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
    return redirect(url_for('inicio'))

@app.route('/arquivar/<int:id>', methods=['POST'])
@login_required
def arquivar_entrada(id):
    entrada = Entrada.query.get_or_404(id)
    entrada.arquivado = True
    db.session.commit()
    socketio.emit('update_data')
    flash(f'{entrada.tipo} #{entrada.numero_pedido} foi arquivado com sucesso.', 'success')
    return redirect(url_for('inicio'))

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

@app.route('/relatorio-romaneio', methods=['GET', 'POST'])
@login_required
def relatorio_romaneio():
    if request.method == 'POST':
        if 'pdf_file' not in request.files:
            flash('Nenhum ficheiro selecionado.', 'warning')
            return redirect(request.url)
        
        ficheiro = request.files['pdf_file']
        
        if ficheiro.filename == '':
            flash('Nenhum ficheiro selecionado.', 'warning')
            return redirect(request.url)
        
        if ficheiro and ficheiro.filename.lower().endswith('.pdf'):
            try:
                pdf_bytes = ficheiro.read()
                texto_completo = ""
                with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                    for page in doc:
                        # Extrai o texto mantendo algum layout básico
                        texto_completo += page.get_text()

                # --- LÓGICA DE EXTRAÇÃO AVANÇADA ---
                
                relatorios_extraidos = []
                # Divide o documento em blocos de pedidos, usando "Pedido Pedido Cli." como separador
                blocos_pedidos = re.split(r'Pedido\s+Pedido Cli\.', texto_completo, flags=re.IGNORECASE)

                for bloco in blocos_pedidos[1:]: # Ignora o que vem antes do primeiro pedido
                    
                    # 1. Extrai o NOME DO CLIENTE do texto que vem ANTES do cabeçalho do pedido
                    # Padrão: Procura por uma linha com letras maiúsculas que termina com " - VID."
                    cliente_match = re.search(r'\n([A-Z\s\d\.\-]+-\s*VID\..*?)\n', bloco)
                    nome_cliente = cliente_match.group(1).strip() if cliente_match else "Cliente não encontrado"

                    # 2. Extrai os dados do cabeçalho do pedido
                    # Padrão: Procura pela linha de valores que vem logo após o cabeçalho
                    padrao_cabecalho = re.search(r'Tipo\s+Funcionário\s+Data Pedido\s+Data Entrega\s+Peso\s+m²\s+Total\n(.*?)\n', bloco, re.IGNORECASE | re.DOTALL)
                    dados_cabecalho = {}
                    if padrao_cabecalho:
                        # Divide a linha de valores por múltiplos espaços
                        valores = re.split(r'\s{2,}', padrao_cabecalho.group(1).strip())
                        if len(valores) >= 9:
                            dados_cabecalho = {
                                'pedido': valores[0], 'pedido_cli': valores[1], 'tipo': valores[2],
                                'funcionario': valores[3], 'data_pedido': valores[4], 'data_entrega': valores[5],
                                'peso': valores[6], 'm2': valores[7], 'total': valores[8],
                                'cliente': nome_cliente # Adiciona o cliente que encontrámos
                            }

                    # 3. Extrai a tabela de produtos
                    produtos = []
                    # Padrão para encontrar uma linha de produto, que pode ser complexa
                    padrao_produtos = re.compile(r'(\d{4,})\s+(.*?)\s+OS:(\d+)\s+(\d+x\d+)\s+(\d+)\s+([\d,]+)', re.DOTALL)
                    
                    seccao_produtos_match = re.search(r'Cod\s+Produto\s+LarguraxAltura(.*?)Resumo:', bloco, re.IGNORECASE | re.DOTALL)
                    if seccao_produtos_match:
                        texto_produtos = seccao_produtos_match.group(1)
                        linhas_produtos = padrao_produtos.findall(texto_produtos)
                        for linha in linhas_produtos:
                            produto = {
                                'cod': linha[0].strip(),
                                'produto': linha[1].replace('\n', ' ').strip(),
                                'os': linha[2].strip(),
                                'dimensoes': linha[3].strip(),
                                'qtde': linha[4].strip(),
                                'm2': linha[5].strip()
                            }
                            produtos.append(produto)
                    
                    if dados_cabecalho:
                        relatorios_extraidos.append({
                            'cabecalho': dados_cabecalho,
                            'produtos': produtos
                        })

                if not relatorios_extraidos:
                    flash('Nenhum dado de pedido válido foi encontrado. O formato do PDF pode ser diferente do esperado.', 'warning')
                    return render_template('relatorio_romaneio.html')

                flash(f'{len(relatorios_extraidos)} pedido(s) processado(s) com sucesso!', 'success')
                return render_template('relatorio_romaneio.html', relatorios=relatorios_extraidos)

            except Exception as e:
                flash(f'Ocorreu um erro inesperado ao processar o PDF: {e}', 'danger')
                return redirect(request.url)

    return render_template('relatorio_romaneio.html')

@app.route('/relatorio-pedidos')
@login_required
def relatorio_pedidos():
    """Exibe a página da nova ferramenta de Relatório de Pedidos."""
    # Por enquanto, esta função apenas renderiza a página.
    # A lógica de upload e análise de PDF será adicionada depois.
    return render_template('relatorio_pedidos.html')

@app.route('/cadastro-clientes')
@login_required
def cadastro_clientes():
    """Exibe a página da nova ferramenta de Cadastro de Clientes."""
    # A lógica de cadastro será adicionada futuramente.
    return render_template('cadastro_clientes.html')

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