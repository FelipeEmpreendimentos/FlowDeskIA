# FlowDeskIA — ambiente de staging

Arquitetura de teste:

- PostgreSQL: Supabase
- API FastAPI: Render
- Frontend React/Vite: Vercel
- Branch de deploy: `staging`

## 1. Banco Supabase

Para o backend persistente do Render, use preferencialmente a connection string do **Session Pooler** do Supabase na porta `5432`.

Variaveis do backend:

```env
APP_ENV=production
DATABASE_URL=postgresql://...
DB_SSLMODE=require
SQL_ECHO=false
```

`DATABASE_URL` substitui `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASSWORD`. O formato separado continua funcionando no desenvolvimento local.

### Inicializar um projeto vazio

Com `DATABASE_URL` e `DB_SSLMODE=require` configurados no ambiente do backend:

```powershell
python -m scripts.init_remote_database
```

O comando e idempotente: cria enums/tabelas ausentes e depois executa os ajustes do `scripts.setup_release`.

Depois, para criar a primeira empresa/administrador de teste, use o bootstrap existente:

```powershell
python scripts/bootstrap.py --empresa "FlowDeskIA Teste" --cnpj "00000000000000" --nome "Felipe" --email "SEU_EMAIL" --senha "SUA_SENHA"
```

## 2. Backend no Render

O repositorio possui `render.yaml` com o servico `flowdeskia-api-staging`.

Configuracao principal:

- branch: `staging`
- runtime: Python
- build: `pip install -r requirements.txt`
- start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- health check: `/api/v1/system/ready`
- auto deploy: somente depois dos checks do GitHub passarem

Secrets/variaveis a preencher no Render:

```text
DATABASE_URL
FRONTEND_URL
CORS_ORIGINS
OPENAI_API_KEY
```

O `JWT_SECRET` e gerado pelo Blueprint do Render. Nao coloque chaves reais no repositorio.

Quando a URL do frontend existir, configure por exemplo:

```text
FRONTEND_URL=https://SEU-FRONTEND.vercel.app
CORS_ORIGINS=https://SEU-FRONTEND.vercel.app
```

## 3. Frontend na Vercel

Ao importar o repositorio na Vercel:

- Root Directory: `frontend`
- Framework Preset: Vite
- Build Command: `npm run build`
- Output Directory: `dist`
- branch de staging: `staging`

Variavel obrigatoria:

```text
VITE_API_URL=https://SEU-BACKEND.onrender.com/api/v1
```

O arquivo `frontend/vercel.json` faz o fallback das rotas da SPA para `index.html`, permitindo abrir URLs internas diretamente no navegador.

## 4. Ordem do primeiro deploy

1. Criar o projeto no Supabase.
2. Obter a connection string do Session Pooler.
3. Inicializar o banco com `python -m scripts.init_remote_database`.
4. Criar a branch `staging` no GitHub.
5. Criar o backend pelo Blueprint do Render e informar os secrets.
6. Criar o frontend na Vercel com Root Directory `frontend`.
7. Configurar `VITE_API_URL` na Vercel.
8. Voltar ao Render e preencher `FRONTEND_URL` e `CORS_ORIGINS` com a URL da Vercel.
9. Validar `/api/v1/system/ready`, login, telas principais e resposta da IA.

## Observacao sobre uploads

Hoje logos e arquivos enviados pela API usam o filesystem local do backend. Em um servico sem disco persistente, esses arquivos podem desaparecer em redeploys. Isso nao impede o staging inicial, mas antes da producao os uploads devem migrar para storage persistente (por exemplo, Supabase Storage).
