# create_user.py

from app import app, db, User, bcrypt
from getpass import getpass

def setup_database():
    with app.app_context():
        db.create_all()

def create_admin_user():
    username = input("Digite o nome de utilizador do ADMIN: ")
    password = getpass("Digite a senha do ADMIN: ")
    
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password_hash=hashed_password, is_admin=True)

    with app.app_context():
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"Erro: O utilizador '{username}' já existe.")
        else:
            db.session.add(new_user)
            db.session.commit()
            print(f"Utilizador ADMINISTRADOR '{username}' criado com sucesso!")

if __name__ == '__main__':
    print("A configurar a base de dados...")
    setup_database()
    print("Base de dados pronta.")
    print("-" * 20)
    create_admin_user()