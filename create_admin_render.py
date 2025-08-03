# create_admin_render.py
import os
from app import app, db, User, bcrypt

# Lê as credenciais das variáveis de ambiente
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    print("Erro: As variáveis de ambiente ADMIN_USERNAME e ADMIN_PASSWORD precisam ser definidas.")
else:
    with app.app_context():
        print(f"Verificando se o utilizador '{ADMIN_USERNAME}' já existe...")
        existing_user = User.query.filter_by(username=ADMIN_USERNAME).first()
        if existing_user:
            print(f"O utilizador '{ADMIN_USERNAME}' já existe.")
        else:
            print(f"Criando o utilizador '{ADMIN_USERNAME}'...")
            hashed_password = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf-8')
            new_user = User(username=ADMIN_USERNAME, password_hash=hashed_password, is_admin=True)
            db.session.add(new_user)
            db.session.commit()
            print(f"Utilizador ADMINISTRADOR '{ADMIN_USERNAME}' criado com sucesso!")