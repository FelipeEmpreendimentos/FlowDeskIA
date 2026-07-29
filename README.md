# FlowDeskIA — Backend MVP

Este pacote usa as tabelas PostgreSQL V2.1 que você já criou. Ele **não**
executa `CREATE TABLE` e não apaga o banco.

## O que está implementado

- Conexão com PostgreSQL e teste de saúde.
- Login com token JWT.
- Perfis ADMIN, GERENTE e FUNCIONARIO.
- Separação de dados por empresa.
- Empresa e usuários.
- Clientes e veículos.
- Serviços.
- Agendamentos, conflito de horários e consulta de disponibilidade.
- Horários recorrentes e bloqueios da agenda.
- Conversas e mensagens.
- Configuração e memória da IA.
- Cadastro das integrações.
- Notificações, dashboard, assinaturas e logs.
- Documentação automática pelo Swagger.

## O que ainda depende de uma decisão externa

O envio real para WhatsApp e a chamada de uma IA não são ativados neste
pacote, porque ainda é preciso escolher o provedor e fornecer credenciais.
A estrutura do banco e os pontos de configuração já estão preparados.

## 1. Antes de substituir os arquivos

Pare o Uvicorn no terminal:

```powershell
Ctrl + C
```

Faça uma cópia da pasta atual `app`, caso deseje voltar.

## 2. Extração

Extraia o conteúdo deste ZIP diretamente dentro da pasta `FlowDeskIA`.

A estrutura ficará assim:

```text
FlowDeskIA/
├── app/
├── scripts/
├── .env
├── .env.example
├── .venv/
├── requirements.txt
└── README.md
```

A pasta `.venv` não deve ser apagada.

## 3. Atualizar o arquivo .env

Mantenha os dados do PostgreSQL que já funcionam e acrescente:

```env
APP_NAME=FlowDeskIA
APP_ENV=development
SQL_ECHO=false

JWT_SECRET=uma_chave_grande_e_aleatoria
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=480

CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

Para gerar uma chave no PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copie o resultado para `JWT_SECRET`.

## 4. Instalar as dependências novas

Com `(.venv)` aparecendo no terminal:

```powershell
pip install -r requirements.txt
```

## 5. Verificar os arquivos

```powershell
python scripts/check_imports.py
```

## 6. Criar a empresa e o primeiro administrador

Execute em uma única linha, trocando os dados:

```powershell
python scripts/bootstrap.py --empresa "Lava Car dos Irmaos" --cnpj "00000000000000" --nome "Felipe" --email "felipe@teste.com" --senha "SenhaForte123"
```

O script mostrará o `Empresa ID`. Guarde esse número porque ele será usado
no login.

Caso a empresa já exista com o mesmo CNPJ, o script somente cria o
administrador nela.

## 7. Iniciar o backend

```powershell
uvicorn app.main:app --reload
```

## 8. Abrir no navegador

- API: `http://127.0.0.1:8000`
- Documentação: `http://127.0.0.1:8000/docs`
- Banco: `http://127.0.0.1:8000/api/v1/system/database`

## 9. Fazer o primeiro login no Swagger

Em `/docs`, abra:

```text
POST /api/v1/auth/login
```

Use:

```json
{
  "empresa_id": 1,
  "email": "felipe@teste.com",
  "senha": "SenhaForte123"
}
```

Copie o `access_token`.

Clique em **Authorize**, no topo da documentação, e cole apenas o token.
Depois disso, os demais endpoints estarão liberados conforme o cargo.

## Observações importantes

- O endpoint DELETE de clientes apenas muda o status para INATIVO.
- O endpoint DELETE de serviços apenas desativa o serviço.
- O endpoint DELETE de agendamentos cancela o agendamento.
- O token das integrações pode ser gravado, mas nunca é devolvido pelas
  respostas da API.
- Não publique o arquivo `.env`.
