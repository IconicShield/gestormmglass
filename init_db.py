# init_db.py
from app import app, db

print("Iniciando a criação do banco de dados...")

# O app_context é necessário para que o SQLAlchemy saiba a qual banco de dados se conectar
with app.app_context():
    db.create_all()

print("Banco de dados e tabelas criados com sucesso!")