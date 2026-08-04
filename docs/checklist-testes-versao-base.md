# Checklist de testes — versão base do FlowDeskIA

Use este roteiro depois de executar `python -m scripts.setup_release` e iniciar backend e frontend com `localhost`.

## 1. Acesso e sessão

- [ ] Entrar com Administrador, Gerente e Funcionário.
- [ ] Confirmar mensagem de erro com senha incorreta.
- [ ] Validar preenchimento de e-mail e senha salvos pelo navegador.
- [ ] Entrar com **Lembre de mim** desmarcado, fechar e reabrir o navegador.
- [ ] Entrar com **Lembre de mim** marcado, fechar e reabrir o navegador.
- [ ] Sair da conta e confirmar que a sessão lembrada foi removida.
- [ ] Recuperar e redefinir senha.
- [ ] Confirmar bloqueio de usuário, empresa inativa ou empresa suspensa.

## 2. Visão geral

- [ ] Conferir os indicadores apresentados.
- [ ] Confirmar que agendamentos finalizados e cancelados não aparecem em **Próximos atendimentos**.
- [ ] Finalizar ou cancelar um agendamento e voltar à Visão Geral.
- [ ] Confirmar atualização da lista ao retornar para a janela.
- [ ] Testar os atalhos para novo agendamento, cliente, conversas e serviços.
- [ ] Abrir as notificações pelo sino e retornar à tela anterior.

## 3. Agenda e disponibilidade

- [ ] Criar agendamento escolhendo um funcionário específico.
- [ ] Criar agendamento com **Qualquer funcionário**.
- [ ] Confirmar que o profissional sugerido aparece antes de salvar.
- [ ] Confirmar distribuição para quem possui menor carga disponível no dia.
- [ ] Validar duração do serviço e horário final.
- [ ] Validar jornadas, pausas, bloqueios e fim do expediente.
- [ ] Testar intervalos de 15, 30 e 60 minutos.
- [ ] Confirmar que horários passados não aparecem no dia atual.
- [ ] Cancelar um agendamento e reutilizar imediatamente o horário.
- [ ] Finalizar antes do horário previsto e reutilizar imediatamente o período liberado.
- [ ] Editar cliente, serviço, veículo, profissional, data e horário.
- [ ] Confirmar que **Cancelado** não aparece na criação.
- [ ] Testar os modais de início, cancelamento e finalização.
- [ ] Validar notificações e histórico gerados pelas ações.

## 4. Conversas com clientes

- [ ] Confirmar as abas compactas **Conversas** e **Histórico**.
- [ ] Confirmar **Meus**, **IA** e **Geral** dentro do painel da lista.
- [ ] Validar os contadores dos três grupos.
- [ ] Buscar por cliente, WhatsApp e responsável.
- [ ] Combinar busca, grupo e situação da conversa.
- [ ] Criar conversa iniciada pela IA.
- [ ] Criar conversa atribuída a uma pessoa.
- [ ] Assumir, transferir e devolver uma conversa à fila.
- [ ] Ativar e pausar a IA em uma conversa.
- [ ] Enviar mensagem com Enter e quebrar linha com Shift + Enter.
- [ ] Marcar mensagens do cliente como lidas.
- [ ] Finalizar com e sem solicitação de avaliação.
- [ ] Consultar resumo, responsável e avaliação no Histórico.
- [ ] Reabrir e confirmar retorno para **Meus**.

## 5. Chat interno

- [ ] Abrir o grupo Geral da empresa.
- [ ] Criar conversa direta.
- [ ] Criar grupo e selecionar participantes.
- [ ] Enviar mensagens e validar atualização automática.
- [ ] Confirmar contadores de não lidas.
- [ ] Confirmar isolamento entre empresas.
- [ ] Validar busca, abas Conversas e Grupos e retorno no celular.
- [ ] Confirmar dica de Shift + Enter e contador alinhados.

## 6. Clientes e veículos

- [ ] Cadastrar, editar, desativar e reativar cliente.
- [ ] Confirmar que funcionário não altera situações restritas.
- [ ] Cadastrar e editar veículo.
- [ ] Excluir veículo usando o modal do sistema.
- [ ] Confirmar atualização das listas e mensagens de sucesso.
- [ ] Validar vínculo correto entre cliente e veículos.

## 7. Serviços

- [ ] Cadastrar serviço com preço, duração e cor.
- [ ] Editar e desativar serviço.
- [ ] Configurar adicionais por tipo de veículo.
- [ ] Confirmar cálculo do valor no agendamento.
- [ ] Validar modo somente consulta para quem não pode gerenciar.

## 8. Financeiro

- [ ] Confirmar abertura padrão em **Este mês**.
- [ ] Testar Hoje, Esta semana, Este mês e datas manuais.
- [ ] Conferir valor final, recebido, pendente, descontos e cortesias.
- [ ] Abrir detalhes de um fechamento.
- [ ] Registrar pagamento integral e parcial.
- [ ] Testar formas de pagamento.
- [ ] Aplicar desconto por valor e percentual.
- [ ] Registrar cortesia.
- [ ] Estornar pagamento usando o modal do sistema.
- [ ] Confirmar recálculo do saldo após estorno.
- [ ] Validar ações somente de visualização e de gerenciamento.

## 9. Relatórios

- [ ] Testar todos os períodos rápidos e datas manuais.
- [ ] Conferir faturamento, recebido, pendente, ticket e recorrência.
- [ ] Validar gráfico diário de faturamento e recebimentos.
- [ ] Validar distribuição do faturamento por serviço.
- [ ] Confirmar que os gráficos mudam com o período.
- [ ] Conferir tabelas de Serviços e Equipe.
- [ ] Conferir avaliações, média, distribuição e comentários.
- [ ] Validar bloqueio de avaliações quando não incluídas no plano.

## 10. Equipe, jornadas e bloqueios

- [ ] Cadastrar Administrador, Gerente e Funcionário.
- [ ] Editar e desativar usuário.
- [ ] Criar e alterar jornada.
- [ ] Usar apenas **Ver detalhes** no cartão da jornada.
- [ ] Criar pausas e bloqueios de agenda.
- [ ] Confirmar impacto na disponibilidade.

## 11. Módulos e permissões

- [ ] Desativar um módulo e confirmar remoção do menu para todos.
- [ ] Confirmar bloqueio da API do módulo desativado.
- [ ] Reativar e confirmar retorno dos dados existentes.
- [ ] Testar **Visualizar** como Padrão, Liberar e Bloquear.
- [ ] Testar **Gerenciar** como Padrão, Liberar e Bloquear.
- [ ] Liberar visualização sem gerenciamento e tentar uma ação administrativa.
- [ ] Liberar gerenciamento para funcionário de confiança.
- [ ] Confirmar que o cargo original não foi alterado.
- [ ] Bloquear individualmente um módulo normalmente permitido pelo cargo.
- [ ] Confirmar registro das alterações no Histórico de atividades.

## 12. Notificações

- [ ] Marcar uma notificação como lida.
- [ ] Marcar todas como lidas.
- [ ] Ativar e desativar categorias individualmente.
- [ ] Usar **Desativar todas** e confirmar gravação imediata.
- [ ] Recarregar a página e confirmar que todas permanecem desligadas.
- [ ] Reativar categorias e salvar preferências.

## 13. Histórico de atividades

- [ ] Confirmar abertura padrão em **Hoje**.
- [ ] Testar Hoje, Esta semana, Este mês e intervalo manual.
- [ ] Buscar pelo texto exibido da ação, como “cancelou” ou “cadastrou”.
- [ ] Buscar por usuário, área e identificador com ou sem `#`.
- [ ] Combinar busca, datas, usuário e área.
- [ ] Confirmar alinhamento e tamanho do campo de busca.
- [ ] Abrir e ocultar detalhes de uma atividade.

## 14. Plano e consumo

- [ ] Conferir plano, status, vencimento e teste.
- [ ] Conferir recursos disponíveis e indisponíveis.
- [ ] Validar consumo e limites.
- [ ] Confirmar bloqueio ao atingir limites configurados.

## 15. Super Admin

- [ ] Entrar e sair pelo acesso exclusivo do Super Admin.
- [ ] Validar preenchimento de credenciais salvas pelo navegador.
- [ ] Conferir indicadores e filtros da Visão Geral.
- [ ] Conferir empresas ativas, testes, suspensas e inadimplentes.
- [ ] Conferir estimativas de receita contratada e projeção anual.
- [ ] Conferir alertas e auditoria recente.
- [ ] Buscar empresa por nome, CNPJ e e-mail.
- [ ] Criar, editar, suspender, reativar e arquivar empresa.
- [ ] Alterar plano, período de teste e limites.
- [ ] Confirmar que Essencial e Profissional possuem IA apenas como adicional.
- [ ] Ativar e desativar o adicional de IA por empresa.
- [ ] Conferir auditoria global.

## 16. Responsividade e acabamento

- [ ] Testar computador, tablet e celular.
- [ ] Abrir e fechar o menu lateral no celular.
- [ ] Conferir tabelas convertidas em cartões.
- [ ] Conferir modais sem cortes e com rolagem adequada.
- [ ] Navegar por teclado e verificar foco visível.
- [ ] Confirmar que textos, contadores, buscas e botões não se sobrepõem.

## 17. Fluxo completo de operação

- [ ] Criar empresa e administrador pelo Super Admin.
- [ ] Configurar plano, módulos, agenda, equipe, serviços e permissões.
- [ ] Cadastrar cliente e veículo.
- [ ] Criar atendimento por funcionário específico e por distribuição automática.
- [ ] Iniciar e finalizar o atendimento.
- [ ] Registrar pagamento e conferir Financeiro e Relatórios.
- [ ] Criar e finalizar conversa com o cliente.
- [ ] Conferir notificações, histórico e indicadores finais.
- [ ] Repetir o fluxo como Funcionário com permissões limitadas.

Registre cada problema com tela, usuário, passos para reproduzir, resultado esperado, resultado obtido e imagem quando necessário.
