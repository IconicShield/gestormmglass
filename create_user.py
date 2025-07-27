# create_user.py

from app import app, db, User, bcrypt
from getpass import getpass

# --- INÍCIO DA CORREÇÃO ---
# Esta função irá garantir que todas as tabelas (User, Entrada, etc.)
# sejam criadas na base de dados antes de tentarmos usá-las.
def setup_database():
    with app.app_context():
        db.create_all()
# --- FIM DA CORREÇÃO ---

def create_user():
    username = input("Digite o nome de utilizador: ")
    password = getpass("Digite a senha: ")
    password_confirm = getpass("Confirme a senha: ")

    if password != password_confirm:
        print("As senhas não coincidem. Operação cancelada.")
        return

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password_hash=hashed_password)

    with app.app_context():
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"Erro: O utilizador '{username}' já existe.")
        else:
            db.session.add(new_user)
            db.session.commit()
            print(f"Utilizador '{username}' criado com sucesso!")

# --- FLUXO PRINCIPAL ATUALIZADO ---
if __name__ == '__main__':
    print("A configurar a base de dados...")
    setup_database() # Primeiro, chama a função para criar as tabelas
    print("Base de dados pronta.")
    print("-" * 20)
    create_user() # Depois, executa a criação do utilizador