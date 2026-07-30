# Super Admin e planos do FlowDeskIA

## Estrutura de acesso

O Super Admin é uma conta da plataforma, sem vínculo com uma empresa. Seu token é separado dos tokens de administradores, gerentes e funcionários.

- Login das empresas: `/login`
- Login do Super Admin: `/super-admin/login`
- Rotas da API do Super Admin: `/api/v1/super-admin/*`

Um token de Super Admin não funciona nas rotas internas das empresas, e um token de empresa não funciona nas rotas do Super Admin.

## Planos padrão

O comando de preparação cria quatro planos iniciais:

- Essencial
- Profissional
- Inteligente
- Personalizado

Todos os planos são editáveis no painel. Os valores iniciais ficam em R$ 0,00 para que o proprietário defina os preços comerciais depois.

O período de teste padrão é de 14 dias e pode ser alterado por plano ou individualmente por empresa.

A inteligência artificial pode ser contratada como adicional desde o plano Essencial. No plano Inteligente, ela já vem incluída por padrão.

## Recursos e limites

Cada plano pode controlar:

- usuários;
- clientes;
- agendamentos mensais;
- conversas mensais;
- mensagens mensais de IA;
- canais conectados;
- armazenamento;
- agenda, clientes, veículos, serviços e conversas;
- WhatsApp e Instagram;
- avaliações, relatórios e automações;
- múltiplas unidades;
- suporte prioritário.

O Super Admin pode substituir recursos e limites para uma empresa específica sem criar outro plano.

O backend bloqueia recursos que não pertencem ao plano e fiscaliza a criação de usuários, clientes, agendamentos, conversas e canais quando a franquia configurada é atingida. Os contadores de mensagens de IA e armazenamento também ficam disponíveis no painel para a evolução das integrações reais.

## Preparação local após o merge

Atualize o projeto e ative o ambiente virtual:

```powershell
cd "C:\Users\felip\OneDrive\Área de Trabalho\FlowDeskIA"
git pull origin main
.\.venv\Scripts\Activate.ps1
```

Crie as tabelas da plataforma, os planos padrão e sua primeira conta de Super Admin:

```powershell
python -m scripts.setup_super_admin --nome "Felipe" --email "SEU_EMAIL" --senha "SUA_SENHA_FORTE"
```

A senha deve ter no mínimo oito caracteres. Não coloque a senha no GitHub, no `.env.example` ou em arquivos do projeto.

O comando é idempotente: pode ser executado novamente sem duplicar as tabelas e sem substituir planos que já foram editados. Para trocar a senha da conta existente pelo terminal:

```powershell
python -m scripts.setup_super_admin --nome "Felipe" --email "SEU_EMAIL" --senha "NOVA_SENHA_FORTE" --atualizar-senha
```

Valide e inicie o backend:

```powershell
python -m scripts.check_imports
uvicorn app.main:app --reload
```

Em outro terminal, inicie o frontend:

```powershell
cd "C:\Users\felip\OneDrive\Área de Trabalho\FlowDeskIA\frontend"
npm install
npm run dev
```

Abra:

```text
http://localhost:5173/super-admin/login
```

## Funcionalidades do painel

- dashboard da plataforma;
- cadastro de empresas com primeiro administrador;
- alteração de plano, período de teste e status;
- suspensão e reativação de acesso;
- edição completa dos planos;
- IA incluída ou vendida como adicional;
- configuração da IA por empresa;
- recursos e limites personalizados;
- uso mensal por empresa;
- auditoria das ações do Super Admin.

## Segurança

- nenhuma conta de Super Admin possui cadastro público;
- a primeira conta é criada somente pelo terminal;
- senhas são armazenadas com hash;
- credenciais não são devolvidas pela API;
- ações críticas ficam registradas em `super_admin_logs`;
- empresas suspensas, canceladas ou arquivadas não conseguem entrar no painel comum.
