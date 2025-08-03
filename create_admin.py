# create_admin.py
from getpass import getpass
from app import app, db, User, bcrypt

print("--- Criando Usuário Administrador ---")

with app.app_context():
    try:
        username = input("Digite o nome de utilizador do ADMIN: ")
        password = getpass("Digite a senha do ADMIN: ")

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"Erro: O utilizador '{username}' já existe.")
        else:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(username=username, password_hash=hashed_password, is_admin=True)
            db.session.add(new_user)
            db.session.commit()
            print(f"Utilizador ADMINISTRADOR '{username}' criado com sucesso!")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        db.session.rollback()