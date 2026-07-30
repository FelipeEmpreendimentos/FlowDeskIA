# Financeiro do FlowDeskIA

## Objetivo

O módulo financeiro completa o ciclo do atendimento:

1. o agendamento é criado;
2. o serviço é executado;
3. o agendamento é finalizado;
4. um fechamento financeiro é criado;
5. pagamentos, descontos e pendências são registrados;
6. os valores ficam disponíveis para relatórios.

## Instalação local

Depois que a alteração entrar na `main`, execute uma única vez:

```powershell
cd "C:\Users\felip\OneDrive\Área de Trabalho\FlowDeskIA"
.\.venv\Scripts\Activate.ps1
python -m scripts.setup_financeiro
```

O comando é idempotente: pode ser executado novamente sem apagar os dados existentes.

Ele cria:

- `fechamentos_financeiros`;
- `pagamentos_atendimento`;
- índices de consulta;
- fechamentos pendentes para agendamentos antigos já finalizados;
- um gatilho que cria automaticamente o fechamento pendente quando um agendamento é finalizado.

## Situações financeiras

- `PENDENTE`: nenhum valor recebido;
- `PARCIAL`: parte do valor foi recebida;
- `PAGO`: valor final totalmente recebido;
- `CORTESIA`: atendimento sem cobrança;
- `ESTORNADO`: reservado para fechamento completamente estornado.

## Permissões

### Administrador e gerente

- registrar pagamentos;
- conceder desconto;
- marcar cortesia;
- ajustar o fechamento;
- estornar pagamentos.

### Funcionário

- visualizar os fechamentos da empresa;
- registrar pagamento de atendimento próprio ou ainda sem responsável;
- não pode conceder desconto, cortesia ou realizar estorno.

A API sempre valida o `empresa_id`, impedindo acesso a fechamentos e pagamentos de outra empresa.

## Pagamento dividido

Um mesmo fechamento pode receber vários pagamentos, por exemplo:

- R$ 50,00 em PIX;
- R$ 39,90 em dinheiro.

O fechamento é atualizado automaticamente para `PARCIAL` ou `PAGO`.

## Rotas principais

- `GET /api/v1/financeiro/resumo`;
- `GET /api/v1/financeiro/fechamentos`;
- `GET /api/v1/financeiro/agendamentos/{id}/fechamento`;
- `POST /api/v1/financeiro/agendamentos/{id}/fechamento`;
- `POST /api/v1/financeiro/fechamentos/{id}/pagamentos`;
- `PATCH /api/v1/financeiro/fechamentos/{id}`;
- `POST /api/v1/financeiro/pagamentos/{id}/estornar`.

## Auditoria

São registrados no histórico:

- fechamento do atendimento;
- registro de pagamento;
- ajuste de desconto ou cortesia;
- estorno de pagamento.
