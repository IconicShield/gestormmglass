// Teste de sintaxe JavaScript

// Função global para gerar relatório
window.gerarRelatorio = async function(entradaId) {
    // Coletar dados do formulário
    const data = document.getElementById(`relatorio-data-${entradaId}`).value;
    const numeroPedido = document.getElementById(`relatorio-numero-pedido-${entradaId}`).value;
    const numeroCliente = document.getElementById(`relatorio-numero-cliente-${entradaId}`).value;
    const nomeCliente = document.getElementById(`relatorio-nome-cliente-${entradaId}`).value;
    const obra = document.getElementById(`relatorio-obra-${entradaId}`).value;
    
    // Coletar anexos selecionados
    const anexosSelecionados = [];
    const anexosData = [];
    const checkboxes = document.querySelectorAll(`#relatorioModal-${entradaId} input[name="anexos_selecionados"]:checked`);
    
    // Buscar dados dos anexos selecionados
    try {
        const response = await fetch(`/api/entrada/${entradaId}/anexos`);
        const result = await response.json();
        
        if (result.success) {
            checkboxes.forEach(checkbox => {
                const anexoId = parseInt(checkbox.value);
                const anexo = result.anexos.find(a => a.id === anexoId);
                if (anexo) {
                    anexosSelecionados.push(anexoId);
                    anexosData.push(anexo);
                }
            });
        }
    } catch (error) {
        console.error('Erro ao buscar anexos:', error);
    }
    
    // Fechar modal de configuração
    $(`#relatorioModal-${entradaId}`).modal('hide');
    
    // Criar modal de visualização do relatório
    criarModalRelatorio({
        entradaId,
        data,
        numeroPedido,
        numeroCliente,
        nomeCliente,
        obra,
        anexos: anexosData
    });
}

function criarModalRelatorio(dados) {
    const modalId = 'relatorioVisualizacao-' + dados.entradaId;
    
    // Remover modal existente se houver
    const modalExistente = document.getElementById(modalId);
    if (modalExistente) {
        modalExistente.remove();
    }
    
    // Formatar data para exibição
    const dataFormatada = new Date(dados.data + 'T00:00:00').toLocaleDateString('pt-BR');
    
    // Gerar HTML dos anexos
    let anexosHTML = '';
    if (dados.anexos && dados.anexos.length > 0) {
        anexosHTML = '<div class="anexos-section">';
        anexosHTML += '<div class="anexos-title"><i class="fas fa-images"></i> Anexos do Pedido</div>';
        
        dados.anexos.forEach(function(anexo) {
            if (anexo.filename.toLowerCase().match(/\.(png|jpg|jpeg|gif|bmp|webp)$/)) {
                anexosHTML += '<div class="text-center mb-4">';
                anexosHTML += '<img src="/uploads/' + anexo.filename + '" class="relatorio-imagem" alt="' + anexo.filename + '" style="max-width: 100%; height: auto; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">';
                anexosHTML += '<div class="mt-2 text-muted"><small>' + anexo.filename + '</small></div>';
                anexosHTML += '</div>';
            }
        });
        
        anexosHTML += '</div>';
    }
    
    let modalHTML = '<div class="modal fade" id="' + modalId + '" tabindex="-1" role="dialog" aria-labelledby="' + modalId + 'Label" aria-hidden="true">';
    modalHTML += '<div class="modal-dialog modal-xl" role="document">';
    modalHTML += '<div class="modal-content">';
    modalHTML += '<div class="modal-header">';
    modalHTML += '<h5 class="modal-title" id="' + modalId + 'Label"><i class="fas fa-file-alt"></i> Relatório do Pedido</h5>';
    modalHTML += '<div class="ml-auto d-flex">';
    modalHTML += '<button type="button" class="btn btn-primary btn-sm mr-2" onclick="imprimirRelatorio(\'' + modalId + '\')">';
    modalHTML += '<i class="fas fa-print"></i> Imprimir</button>';
    modalHTML += '<button type="button" class="btn btn-success btn-sm mr-2" onclick="baixarPDFRelatorio(\'' + modalId + '\', \'' + dados.numeroPedido + '\')">';
    modalHTML += '<i class="fas fa-download"></i> Download PDF</button>';
    modalHTML += '<button type="button" class="close" data-dismiss="modal" aria-label="Close">';
    modalHTML += '<span aria-hidden="true">&times;</span></button></div></div>';
    modalHTML += '<div class="modal-body" id="' + modalId + '-content">';
    modalHTML += '<div class="relatorio-container" style="background: white; border-radius: 8px; overflow: hidden;">';
    modalHTML += '<div class="relatorio-content" style="padding: 30px;">';
    modalHTML += '<div class="info-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px;">';
    
    // Data da Entrada
    modalHTML += '<div class="info-item" style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff;">';
    modalHTML += '<div class="info-label" style="font-weight: 600; color: #495057; font-size: 0.9em; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">Data da Entrada</div>';
    modalHTML += '<div class="info-value" style="font-size: 1.1em; color: #212529; font-weight: 500;">' + dataFormatada + '</div></div>';
    
    // Número do Pedido
    modalHTML += '<div class="info-item" style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff;">';
    modalHTML += '<div class="info-label" style="font-weight: 600; color: #495057; font-size: 0.9em; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">Número do Pedido</div>';
    modalHTML += '<div class="info-value" style="font-size: 1.1em; color: #212529; font-weight: 500;">' + dados.numeroPedido + '</div></div>';
    
    // Número do Cliente
    modalHTML += '<div class="info-item" style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff;">';
    modalHTML += '<div class="info-label" style="font-weight: 600; color: #495057; font-size: 0.9em; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">Número do Cliente</div>';
    modalHTML += '<div class="info-value" style="font-size: 1.1em; color: #212529; font-weight: 500;">' + dados.numeroCliente + '</div></div>';
    
    // Nome do Cliente
    modalHTML += '<div class="info-item" style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff;">';
    modalHTML += '<div class="info-label" style="font-weight: 600; color: #495057; font-size: 0.9em; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">Nome do Cliente</div>';
    modalHTML += '<div class="info-value" style="font-size: 1.1em; color: #212529; font-weight: 500;">' + dados.nomeCliente + '</div></div>';
    
    modalHTML += '</div>';
    
    // Obra (se existir)
    if (dados.obra) {
        modalHTML += '<div class="info-item" style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; margin-bottom: 30px;">';
        modalHTML += '<div class="info-label" style="font-weight: 600; color: #495057; font-size: 0.9em; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">Obra</div>';
        modalHTML += '<div class="info-value" style="font-size: 1.1em; color: #212529; font-weight: 500;">' + dados.obra + '</div></div>';
    }
    
    modalHTML += anexosHTML;
    modalHTML += '</div></div></div></div></div></div>';
    
    // Adicionar modal ao DOM
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Mostrar modal
    $(`#${modalId}`).modal('show');
    
    // Remover modal do DOM quando fechado
    $(`#${modalId}`).on('hidden.bs.modal', function () {
        this.remove();
    });
}

console.log('Sintaxe JavaScript válida!');