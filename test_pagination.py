from app import app, db, Entrada
from flask import request

app.app_context().push()

# Testar paginação de pedidos arquivados
pedidos_query = Entrada.query.filter_by(arquivado=True).filter(Entrada.tipo == 'Pedido')
pedidos_paginados = pedidos_query.order_by(Entrada.data_registro.desc()).paginate(
    page=1, per_page=30, error_out=False
)

print(f'Total pedidos arquivados: {pedidos_paginados.total}')
print(f'Número de páginas: {pedidos_paginados.pages}')
print(f'Tem próxima página: {pedidos_paginados.has_next}')
print(f'Página atual: {pedidos_paginados.page}')
print(f'Itens por página: {pedidos_paginados.per_page}')

# Testar página 2
if pedidos_paginados.has_next:
    pedidos_page2 = pedidos_query.order_by(Entrada.data_registro.desc()).paginate(
        page=2, per_page=30, error_out=False
    )
    print(f'\nPágina 2:')
    print(f'Total itens na página 2: {len(pedidos_page2.items)}')
    print(f'Tem página anterior: {pedidos_page2.has_prev}')