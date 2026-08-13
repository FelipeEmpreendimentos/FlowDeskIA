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

## 4. Chat interno

- Abrir conversas diretas, grupos e o canal Geral da empresa.
- Enviar mensagens e validar atualização automática, não lidas e comportamento mobile.
- Com apenas **Visualizar**, confirmar que conversas diretas e mensagens funcionam, mas o botão de criar grupo não aparece.
- Com **Gerenciar**, criar um grupo e confirmar os participantes.
- Tentar criar grupo sem gerenciamento por uma requisição direta e confirmar o bloqueio do backend.

## 5. Conversas e Histórico

- Confirmar que **Histórico** aparece no menu abaixo de Conversas e acima de Clientes.
- Confirmar que a tela Conversas não mostra abas internas de Conversas/Histórico.
- Conferir a ordem: busca, filtro **Todas as atuais** e depois **Meus, IA e Geral**.
- Testar os grupos Meus, IA e Geral e seus contadores.
- Buscar por cliente e responsável.
- Filtrar conversas abertas e em atendimento.
- Com apenas **Visualizar**, confirmar que Nova conversa não aparece, mas atendimentos existentes continuam acessíveis conforme responsabilidade.
- Com **Gerenciar**, iniciar uma nova conversa.
- Tentar criar conversa sem gerenciamento por uma requisição direta e confirmar o bloqueio do backend.
- Enviar mensagens, trocar responsável, pausar/ativar IA e alterar status conforme o nível permitido.
- Finalizar conversa com e sem solicitação de avaliação.
- Abrir a opção **Histórico** no menu e conferir somente conversas finalizadas.
- Filtrar o histórico por avaliação respondida, pendente e sem avaliação.
- Abrir mensagens e resumo de uma conversa finalizada.
- Reabrir uma conversa e confirmar que ela volta para Conversas.

## 6. Clientes

- Com apenas **Visualizar**, pesquisar e consultar clientes e abrir os veículos do cliente.
- Confirmar que criar, editar e alterar a situação ficam indisponíveis.
- Com **Gerenciar**, cadastrar, editar, desativar e reativar clientes.
- Confirmar que tentativas de alteração sem gerenciamento recebem bloqueio do backend.

## 7. Veículos

- Com apenas **Visualizar**, pesquisar e consultar veículos.
- Confirmar que novo veículo, edição e exclusão ficam indisponíveis.
- Com **Gerenciar**, cadastrar, editar e excluir veículos.
- Confirmar que tentativas de alteração sem gerenciamento recebem bloqueio do backend.

## 8. Serviços

- Com apenas **Visualizar**, pesquisar e consultar serviços ativos e inativos.
- Confirmar que cadastro, edição, desativação e reativação ficam indisponíveis.
- Com **Gerenciar**, cadastrar, editar, desativar e reativar serviços.
- Validar adicionais por tipo de veículo e a limpeza dos adicionais.
- Confirmar que tentativas de alteração sem gerenciamento recebem bloqueio do backend.

## 9. Financeiro

- Confirmar que abre em **Este mês**.
- Entrar como funcionário com Financeiro em **Padrão** ou **Visualizar liberado**.
- Confirmar que aparecem somente fechamentos, valores e pendências dos próprios atendimentos.
- Registrar recebimento de uma pendência própria.
- Confirmar que o funcionário não consegue abrir ou receber fechamento de outro profissional por URL ou requisição direta.
- Liberar **Gerenciar** e confirmar a visualização de todos os atendimentos.
- Com gerenciamento, receber pendências de outros funcionários, ajustar fechamentos e estornar pagamentos.
- Testar Hoje, Esta semana, Este mês e intervalo personalizado.
- Conferir valores recebido, pendente e descontos.

## 10. Relatórios

- Confirmar que o módulo apresenta somente a permissão **Visualizar**.
- Confirmar que não existe opção Gerenciar na configuração do módulo.
- Alterar o período e conferir atualização dos indicadores.
- Conferir gráfico diário de faturamento e recebimentos.
- Conferir distribuição de faturamento por serviço.
- Testar abas Serviços, Equipe e Avaliações.
- Validar comportamento quando Avaliações não estiverem incluídas no plano.

## 11. Equipe

- Com apenas **Visualizar**, confirmar que somente a aba Usuários aparece.
- Confirmar que Jornadas e Bloqueios não aparecem e que ações de alteração ficam indisponíveis.
- Com **Gerenciar**, criar, editar, desativar e reativar funcionários.
- Com gerenciamento, configurar jornadas, pausas e bloqueios.
- Confirmar que tentativas de alteração sem gerenciamento recebem bloqueio do backend.

## 12. Módulos e permissões

- Desativar módulo e confirmar que ele some do menu e bloqueia a API.
- Reativar o módulo.
- Testar Padrão, Liberar e Bloquear em Visualizar e Gerenciar.
- Confirmar que Gerenciar só tem efeito quando Visualizar está disponível.
- Confirmar que as descrições exibidas correspondem ao comportamento de cada módulo.
- Confirmar que Relatórios mostra somente Visualizar.
- Reentrar com o usuário testado depois de cada alteração importante.

## 13. Notificações

- Marcar uma notificação como lida.
- Marcar todas como lidas.
- Desativar uma categoria e salvar.
- Usar **Desativar todas** e confirmar todas as categorias desligadas.
- Reativar categorias e salvar novamente.

## 14. Histórico de atividades

- Confirmar que abre com a data de hoje.
- Testar Hoje, Esta semana e Este mês.
- Buscar por ação exibida, usuário, área e identificador como `#17`.
- Combinar busca com data, usuário e área.
- Abrir e fechar os detalhes das atividades.

## 15. Plano e Super Admin

- Conferir plano, consumo e recursos da empresa.
- Validar limites próximos do máximo.
- Abrir o Super Admin e testar Visão Geral, empresas, planos e auditoria.
- Conferir filtros de período e indicadores financeiros.
- Confirmar que Essencial e Profissional não oferecem IA incluída.
- Confirmar que esses planos permitem IA como adicional.
- Suspender e reativar empresa de teste.
- Validar acesso da empresa após cada mudança de situação.

## 16. Responsividade e fluxo completo

- Testar computador, tablet e celular.
- Abrir e fechar menu lateral no celular.
- Validar tabelas, modais, conversas, chat interno e formulários.
- Simular o fluxo completo: cliente → veículo → serviço → funcionário → agendamento → atendimento → finalização → pagamento → relatório → histórico.
- Registrar qualquer diferença visual, mensagem inesperada ou comportamento lento.
