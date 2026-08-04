# Checklist de testes — Versão base FlowDeskIA

Use este roteiro para validar o sistema antes das integrações com IA e WhatsApp.

## 1. Acesso e sessão

- Entrar com administrador, gerente e funcionário.
- Validar o preenchimento de e-mail e senha salvos pelo navegador.
- Testar **Lembre de mim** marcado e desmarcado.
- Fechar e reabrir o navegador para conferir a sessão lembrada.
- Sair da conta e confirmar que a sessão foi encerrada.
- Repetir o login no Super Admin.

## 2. Visão Geral

- Conferir os indicadores e os atalhos rápidos.
- Criar um agendamento de hoje e confirmar que ele aparece em Próximos atendimentos.
- Finalizar o atendimento e confirmar que ele desaparece da lista.
- Cancelar outro agendamento e confirmar que ele também desaparece.
- Voltar para a janela do sistema e conferir a atualização automática.

## 3. Agenda

- Criar agendamento com um funcionário específico.
- Criar usando **Qualquer funcionário** e conferir a sugestão antes de salvar.
- Validar distribuição entre funcionários disponíveis e com menor carga no dia.
- Testar intervalos de 15, 30 e 60 minutos nas configurações.
- Validar jornada, pausa, bloqueio e fim do expediente.
- Tentar marcar um horário passado no dia atual.
- Cancelar um agendamento e reservar novamente o mesmo horário.
- Finalizar antecipadamente e reservar novamente o horário liberado.
- Editar data, horário, funcionário, cliente, veículo, serviço e observação.
- Conferir que Cancelado não aparece na criação.

## 4. Conversas e Histórico

- Confirmar que **Histórico** aparece no menu abaixo de Conversas e acima de Clientes.
- Confirmar que a tela Conversas não mostra abas internas de Conversas/Histórico.
- Conferir a ordem: busca, filtro **Todas as atuais** e depois **Meus, IA e Geral**.
- Testar os grupos Meus, IA e Geral e seus contadores.
- Buscar por cliente e responsável.
- Filtrar conversas abertas e em atendimento.
- Criar conversa e enviar mensagens.
- Trocar responsável, pausar/ativar IA e alterar status.
- Finalizar conversa com e sem solicitação de avaliação.
- Abrir a opção **Histórico** no menu e conferir somente conversas finalizadas.
- Filtrar o histórico por avaliação respondida, pendente e sem avaliação.
- Abrir mensagens e resumo de uma conversa finalizada.
- Reabrir uma conversa e confirmar que ela volta para Conversas.

## 5. Clientes, veículos e serviços

- Criar, editar, desativar e reativar cliente.
- Buscar cliente por nome, WhatsApp e e-mail.
- Cadastrar e editar veículo.
- Validar vínculo do veículo com o cliente correto.
- Excluir veículo com usuário autorizado.
- Criar e editar serviço, preço, duração e situação.
- Confirmar as limitações visuais e de API para funcionários.

## 6. Financeiro

- Confirmar que abre em **Este mês**.
- Testar Hoje, Esta semana, Este mês e intervalo personalizado.
- Finalizar atendimento e conferir o fechamento financeiro.
- Registrar pagamento total e parcial.
- Aplicar desconto, cortesia e observação.
- Estornar pagamento com confirmação.
- Conferir valores recebido, pendente e descontos.

## 7. Relatórios

- Alterar o período e conferir atualização dos indicadores.
- Conferir gráfico diário de faturamento e recebimentos.
- Conferir distribuição de faturamento por serviço.
- Testar abas Serviços, Equipe e Avaliações.
- Validar comportamento quando Avaliações não estiverem incluídas no plano.

## 8. Equipe, módulos e permissões

- Criar e editar funcionário.
- Configurar jornada, pausas e bloqueios.
- Desativar módulo e confirmar que ele some do menu e bloqueia a API.
- Reativar o módulo.
- Liberar somente **Visualizar** para um funcionário.
- Confirmar que ele consulta a área sem ações administrativas.
- Liberar **Gerenciar** e confirmar as ações permitidas.
- Bloquear Visualizar e confirmar que Gerenciar também não concede acesso isolado.
- Testar Padrão, Liberar e Bloquear em diferentes módulos.

## 9. Notificações

- Marcar uma notificação como lida.
- Marcar todas como lidas.
- Desativar uma categoria e salvar.
- Usar **Desativar todas** e confirmar todas as categorias desligadas.
- Reativar categorias e salvar novamente.

## 10. Histórico de atividades

- Confirmar que abre com a data de hoje.
- Testar Hoje, Esta semana e Este mês.
- Buscar por ação exibida, usuário, área e identificador como `#17`.
- Combinar busca com data, usuário e área.
- Abrir e fechar os detalhes das atividades.

## 11. Plano e Super Admin

- Conferir plano, consumo e recursos da empresa.
- Validar limites próximos do máximo.
- Abrir o Super Admin e testar Visão Geral, empresas, planos e auditoria.
- Conferir filtros de período e indicadores financeiros.
- Confirmar que Essencial e Profissional não oferecem IA incluída.
- Confirmar que esses planos permitem IA como adicional.
- Suspender e reativar empresa de teste.
- Validar acesso da empresa após cada mudança de situação.

## 12. Responsividade e fluxo completo

- Testar computador, tablet e celular.
- Abrir e fechar menu lateral no celular.
- Validar tabelas, modais, conversas, chat interno e formulários.
- Simular o fluxo completo: cliente → veículo → serviço → funcionário → agendamento → atendimento → finalização → pagamento → relatório → histórico.
- Registrar qualquer diferença visual, mensagem inesperada ou comportamento lento.
