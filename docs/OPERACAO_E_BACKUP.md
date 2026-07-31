# Operação, monitoramento e backup do FlowDeskIA

## Preparação da versão

Após atualizar o código, ative o ambiente virtual e execute:

```powershell
cd "C:\Users\felip\OneDrive\Área de Trabalho\FlowDeskIA"
.\.venv\Scripts\Activate.ps1
python -m scripts.setup_release
```

Esse comando é idempotente e prepara:

- Super Admin e planos;
- estrutura financeira;
- fechamento automático de atendimentos;
- onboarding;
- preferências de notificações.

## Verificações de saúde

### Aplicação em execução

```text
GET /api/v1/system/health
```

Retorna `200` quando o processo da API está funcionando.

### Aplicação pronta para atender

```text
GET /api/v1/system/ready
```

Retorna `200` quando a API também consegue consultar o PostgreSQL. Retorna `503` quando o banco está indisponível.

Em produção, o serviço de hospedagem deve usar `/api/v1/system/ready` como verificação de prontidão.

## Identificação de erros

Toda resposta da API recebe o cabeçalho:

```text
X-Request-ID
```

Os logs do backend registram o mesmo identificador, método, caminho, status e duração. Ao investigar um erro informado pelo usuário, procure primeiro pelo `X-Request-ID`.

## Backup manual

O computador precisa ter `pg_dump` disponível no PATH. Ele é instalado junto com as ferramentas do PostgreSQL.

```powershell
python -m scripts.backup_postgres
```

Por padrão, o comando:

- cria um arquivo `.dump` dentro de `backups`;
- cria um `.zip` da pasta `uploads`;
- cria um manifesto `.json` com data e tamanhos;
- mantém 30 dias de arquivos;
- utiliza as credenciais já existentes no `.env`;
- não imprime a senha no terminal.

### Definir outra pasta

```powershell
python -m scripts.backup_postgres --destino "D:\Backups\FlowDeskIA"
```

### Alterar retenção

```powershell
python -m scripts.backup_postgres --reter-dias 60
```

### Salvar apenas o banco

```powershell
python -m scripts.backup_postgres --sem-uploads
```

## Agendamento no Windows

No Agendador de Tarefas do Windows, configure uma tarefa diária executando:

```text
C:\Users\felip\OneDrive\Área de Trabalho\FlowDeskIA\.venv\Scripts\python.exe
```

Argumentos:

```text
-m scripts.backup_postgres --destino "D:\Backups\FlowDeskIA" --reter-dias 30
```

Iniciar em:

```text
C:\Users\felip\OneDrive\Área de Trabalho\FlowDeskIA
```

O backup não deve ficar somente no mesmo computador do sistema. Use uma pasta sincronizada ou armazenamento externo protegido.

## Restauração

A restauração substitui os objetos e dados do banco configurado no `.env`. Pare o backend antes de começar.

```powershell
python -m scripts.restore_postgres `
  --arquivo "D:\Backups\FlowDeskIA\flowdesk_20260730_180000.dump" `
  --confirmar RESTAURAR
```

Depois:

1. execute `python -m scripts.setup_release`;
2. inicie o backend;
3. abra `/api/v1/system/ready`;
4. confira empresas, usuários, agenda e financeiro;
5. restaure o ZIP da pasta `uploads`, quando existir.

## Teste periódico de recuperação

Um backup só é confiável quando consegue ser restaurado. Pelo menos uma vez por mês:

1. crie um banco PostgreSQL separado para teste;
2. aponte temporariamente um `.env` de teste para esse banco;
3. restaure o backup;
4. execute `python -m scripts.setup_release`;
5. confirme o endpoint `/api/v1/system/ready`;
6. confira registros de empresas, agendamentos e pagamentos;
7. remova o banco de teste depois da validação.

Nunca teste restauração diretamente no banco de produção.

## Checklist antes de publicar

- `APP_ENV` configurado como produção;
- `JWT_SECRET` forte e exclusivo;
- PostgreSQL não exposto publicamente sem necessidade;
- CORS limitado ao domínio real do frontend;
- HTTPS ativo;
- SMTP funcionando;
- backup automático configurado;
- restauração testada;
- `/api/v1/system/ready` monitorado;
- logs armazenados fora do processo quando possível;
- `.env`, backups e uploads fora do GitHub;
- conta de Super Admin com senha exclusiva.

## Ordem para investigar indisponibilidade

1. verificar `/api/v1/system/health`;
2. verificar `/api/v1/system/ready`;
3. conferir o serviço do PostgreSQL;
4. procurar o `X-Request-ID` nos logs;
5. verificar espaço em disco;
6. verificar alterações recentes;
7. restaurar backup somente quando a causa exigir recuperação de dados.
