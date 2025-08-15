/**
 * Sistema de Gerenciamento do Painel de Controle
 * Versão revisada e otimizada - 2024
 * 
 * Este arquivo contém todas as funcionalidades do painel de controle
 * organizadas de forma modular e com tratamento robusto de erros.
 */

// Namespace principal do sistema
window.PainelSistema = (function() {
    'use strict';
    
    // Configurações padrão do sistema
    const CONFIG = {
        UPDATE_INTERVAL: 30000, // 30 segundos
        MAX_FAILED_ATTEMPTS: 3,
        DEBOUNCE_DELAY: 50,
        DEBUG_MODE: false,
        THEME_MODE: 'light'
    };
    
    // Estado interno do sistema
    let state = {
        isInitialized: false,
        isInitializing: false,
        autoUpdateActive: true,
        updateInterval: CONFIG.UPDATE_INTERVAL,
        failedAttempts: 0,
        connectionStatus: true,
        lastData: null,
        isManualRefresh: false,
        
        // Controles de sistema
        autoUpdateInterval: null,
        initPromise: null,
        initTimeout: null,
        observers: [],
        statusInterval: null,
        lastUpdateTime: null
    };
    
    // Utilitários de log
    const logger = {
        info: (message) => {
            if (CONFIG.DEBUG_MODE) {
                console.info(`[PainelSistema] ${message}`);
            }
        },
        warn: (message) => {
            console.warn(`[PainelSistema] ${message}`);
        },
        error: (message, error = null) => {
            console.error(`[PainelSistema] ${message}`, error || '');
        }
    };
    
    // Utilitários gerais
    const utils = {
        // Validação de dados
        isValidData: (data) => {
            return data && typeof data === 'object' && !Array.isArray(data);
        },
        
        // Sanitização de HTML
        escapeHtml: (text) => {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        // Formatação de data
        formatDate: (date) => {
            if (!date) return '';
            return new Date(date).toLocaleDateString('pt-BR');
        },
        
        // Debounce function
        debounce: (func, wait) => {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
    };
    
    // Gerenciamento de status
    const statusManager = {
        colorMap: {
            'Não iniciado': 'btn-danger',
            'Em andamento': 'btn-warning',
            'Concluído': 'btn-success'
        },
        
        getStatusColor: (status) => {
            return statusManager.colorMap[status] || 'btn-secondary';
        },
        
        getStatusButtonColor: (status) => {
            const colorMap = {
                'Não iniciado': 'btn-outline-danger',
                'Em andamento': 'btn-outline-warning',
                'Concluído': 'btn-outline-success'
            };
            return colorMap[status] || 'btn-outline-secondary';
        },
        
        updateStatus: async (entryId, newStatus) => {
            try {
                const response = await fetch(`/atualizar-status/${entryId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ status: newStatus })
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    // Atualiza o botão de status na tabela
                    const button = document.getElementById(`status-btn-${entryId}`);
                    if (button) {
                        button.textContent = newStatus;
                        button.className = `btn ${statusManager.getStatusColor(newStatus)} btn-sm dropdown-toggle`;
                    }
                    
                    // Atualiza dashboards se disponível
                    if (data.dashboard && typeof updateDashboards === 'function') {
                        updateDashboards(data.dashboard);
                    }
                    
                    logger.info(`Status atualizado para: ${newStatus}`);
                    return true;
                } else {
                    throw new Error(data.message || 'Erro desconhecido');
                }
            } catch (error) {
                logger.error('Erro ao atualizar status:', error);
                notificationManager.show('Erro ao atualizar o status: ' + error.message, 'error');
                return false;
            }
        }
    };
    
    // Gerenciamento de notificações
    const notificationManager = {
        show: (message, type = 'info', duration = 5000) => {
            try {
                // Verifica se existe função global de notificação
                if (typeof showNotification === 'function') {
                    showNotification(message, type);
                    return;
                }
                
                // Fallback para notificação simples
                const notification = document.createElement('div');
                notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
                notification.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 300px;';
                notification.innerHTML = `
                    ${utils.escapeHtml(message)}
                    <button type="button" class="close" data-dismiss="alert">
                        <span>&times;</span>
                    </button>
                `;
                
                document.body.appendChild(notification);
                
                // Remove automaticamente após o tempo especificado
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, duration);
                
            } catch (error) {
                logger.error('Erro ao exibir notificação:', error);
                // Fallback final
                console.log(`Notificação [${type}]: ${message}`);
            }
        }
    };
    
    // Gerenciamento de conexão
    const connectionManager = {
        updateStatus: (isConnected, serverTime = null) => {
            try {
                state.connectionStatus = isConnected;
                
                const statusElement = document.getElementById('connection-status');
                const lastUpdateElement = document.getElementById('last-update-time');
                
                if (statusElement) {
                    if (isConnected) {
                        statusElement.innerHTML = '<i class="fas fa-circle text-success"></i> Conectado';
                        state.failedAttempts = 0;
                    } else {
                        const attempts = state.failedAttempts > 0 ? ` (${state.failedAttempts} falhas)` : '';
                        statusElement.innerHTML = `<i class="fas fa-circle text-danger"></i> Desconectado${attempts}`;
                    }
                }
                
                if (lastUpdateElement) {
                    const now = serverTime ? new Date(serverTime) : new Date();
                    const timeString = now.toLocaleTimeString('pt-BR');
                    const intervalText = state.updateInterval >= 60000 
                        ? `${state.updateInterval / 60000}min` 
                        : `${state.updateInterval / 1000}s`;
                    
                    lastUpdateElement.textContent = `Última atualização: ${timeString} (${intervalText})`;
                }
                
                state.lastUpdateTime = new Date();
                logger.info(`Status de conexão atualizado: ${isConnected ? 'Conectado' : 'Desconectado'}`);
                
            } catch (error) {
                logger.error('Erro ao atualizar status de conexão:', error);
            }
        }
    };
    
    // API pública do sistema
    return {
        // Inicialização do sistema
        init: function() {
            return new Promise((resolve, reject) => {
                try {
                    if (state.isInitialized) {
                        logger.info('Sistema já inicializado');
                        resolve();
                        return;
                    }
                    
                    if (state.isInitializing) {
                        logger.info('Inicialização já em andamento');
                        if (state.initPromise) {
                            return state.initPromise;
                        }
                    }
                    
                    state.isInitializing = true;
                    state.initPromise = this._performInit();
                    
                    state.initPromise
                        .then(() => {
                            state.isInitialized = true;
                            state.isInitializing = false;
                            logger.info('Sistema inicializado com sucesso');
                            resolve();
                        })
                        .catch((error) => {
                            state.isInitializing = false;
                            logger.error('Falha na inicialização:', error);
                            reject(error);
                        });
                        
                } catch (error) {
                    state.isInitializing = false;
                    logger.error('Erro crítico na inicialização:', error);
                    reject(error);
                }
            });
        },
        
        // Inicialização interna
        _performInit: function() {
            return new Promise((resolve, reject) => {
                try {
                    // Limpa recursos anteriores
                    this.destroy();
                    
                    // Inicializa componentes
                    this._initializeStatusSystem();
                    this._initializeAutoUpdate();
                    this._protectModals();
                    
                    // Configura event listeners
                    this._setupEventListeners();
                    
                    resolve();
                } catch (error) {
                    reject(error);
                }
            });
        },
        
        // Destruição segura do sistema
        destroy: function() {
            try {
                logger.info('Destruindo sistema...');
                
                // Limpa timeouts e intervals
                if (state.initTimeout) {
                    clearTimeout(state.initTimeout);
                    state.initTimeout = null;
                }
                
                if (state.autoUpdateInterval) {
                    clearInterval(state.autoUpdateInterval);
                    state.autoUpdateInterval = null;
                }
                
                if (state.statusInterval) {
                    clearInterval(state.statusInterval);
                    state.statusInterval = null;
                }
                
                // Desconecta observers
                state.observers.forEach(observer => {
                    if (observer && observer.disconnect) {
                        observer.disconnect();
                    }
                });
                state.observers = [];
                
                // Remove event listeners customizados
                document.querySelectorAll('[data-listener-attached]').forEach(element => {
                    element.removeAttribute('data-listener-attached');
                });
                
                // Reset do estado
                state.isInitialized = false;
                state.isInitializing = false;
                state.initPromise = null;
                state.failedAttempts = 0;
                
                logger.info('Sistema destruído com sucesso');
                
            } catch (error) {
                logger.error('Erro ao destruir sistema:', error);
            }
        },
        
        // Getters para estado
        getState: () => ({ ...state }),
        isInitialized: () => state.isInitialized,
        
        // Gerenciadores públicos
        status: statusManager,
        notifications: notificationManager,
        connection: connectionManager,
        utils: utils,
        logger: logger
    };
})();

// Inicialização automática quando o DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        window.PainelSistema.init().catch(error => {
            console.error('Falha na inicialização automática do PainelSistema:', error);
        });
    });
} else {
    // DOM já está pronto
    window.PainelSistema.init().catch(error => {
        console.error('Falha na inicialização automática do PainelSistema:', error);
    });
}

// Proteção contra recarregamentos
window.addEventListener('beforeunload', function() {
    window.PainelSistema.destroy();
});

// Gerenciamento de visibilidade da página
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible' && window.PainelSistema.isInitialized()) {
        // Reaplica proteções quando a página volta a ficar visível
        setTimeout(() => {
            if (typeof protectModals === 'function') protectModals();
            if (typeof restoreAnexosContent === 'function') restoreAnexosContent();
        }, 100);
    }
});