# FlowDeskIA — Matriz de permissões e notificações

## Administrador

Pode administrar toda a operação da empresa: agenda, clientes, veículos,
serviços, conversas, equipe, jornadas, bloqueios, dados da empresa, logo,
integrações, assinatura e auditoria.

Somente administradores podem alterar informações críticas da empresa,
consultar assinatura e consultar logs de auditoria.

## Gerente

Pode administrar a operação: agenda, clientes, veículos, serviços, conversas,
funcionários, jornadas e bloqueios.

Pode criar, editar, ativar e desativar apenas usuários com cargo FUNCIONARIO.
Não pode alterar administradores, outros gerentes, assinatura, auditoria,
integrações nem dados críticos da empresa.

## Funcionário

Pode visualizar toda a agenda da empresa.

Pode criar agendamentos. Em agendamentos existentes, pode alterar somente
status, observações e forma de pagamento quando o atendimento estiver
atribuído a ele ou ainda estiver sem responsável. Não pode cancelar,
reagendar, trocar serviço, trocar preço ou alterar o responsável de um
agendamento existente.

Pode consultar e cadastrar clientes e veículos. Pode corrigir dados básicos,
mas não pode inativar/bloquear clientes nem excluir veículos.

Nas conversas, visualiza atendimentos atribuídos a ele e conversas abertas
sem responsável. Pode assumir e finalizar seus próprios atendimentos, mas não
pode transferir conversas para outros funcionários.

Pode consultar equipe, serviços, jornadas, bloqueios, dados da empresa e suas
próprias notificações. Não pode alterar essas configurações.

## Notificações automáticas

### Funcionário

- novo agendamento atribuído;
- alteração ou cancelamento de atendimento atribuído;
- novo bloqueio ou remoção de bloqueio em sua agenda;
- nova conversa atribuída;
- nova mensagem de cliente em conversa atribuída.

### Gerente

- conversa nova sem responsável;
- cancelamentos;
- criação e remoção de bloqueios;
- tentativas de agendamento com conflito.

### Administrador

Recebe os eventos gerenciais e também:

- criação, edição, ativação e desativação de usuários;
- alterações críticas da empresa e do logo;
- criação e alteração de integrações.

## Inteligência artificial

A configuração da IA será removida do painel comum das empresas. O controle
de ativação, plano, limites e configuração por empresa será feito futuramente
em um painel de plataforma separado, exclusivo do super administrador do
FlowDeskIA.

O super administrador não deve ser implementado como um cargo comum dentro
de uma empresa. Ele deve possuir autenticação, rotas, auditoria e permissões
separadas do ambiente dos clientes.
