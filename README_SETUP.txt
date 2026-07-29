FLOWDESKIA - COMO USAR ESTA ESTRUTURA

1. Extraia o conteúdo deste ZIP dentro da pasta FlowDeskIA.
   A pasta .venv que você já criou deve permanecer como está.

2. Abra o arquivo .env e altere:
   DB_NAME=nome exato do banco criado no pgAdmin
   DB_PASSWORD=senha definida na instalação do PostgreSQL

3. Confirme que o ambiente virtual está ativado.
   O terminal deve começar com:
   (.venv) PS C:\...\FlowDeskIA>

4. Instale as dependências, caso necessário:
   pip install -r requirements.txt

5. Inicie o backend:
   uvicorn app.main:app --reload

6. Abra no navegador:
   API: http://127.0.0.1:8000
   Teste do banco: http://127.0.0.1:8000/health/database
   Documentação automática: http://127.0.0.1:8000/docs

IMPORTANTE

- Não coloque arquivos do projeto dentro da pasta .venv.
- Não envie o arquivo .env para repositórios públicos.
- As pastas models, schemas e services serão preenchidas por etapas.
