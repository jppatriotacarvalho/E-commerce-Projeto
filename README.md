# Projeto E-Commerce — Agente de Análise com IA

Agente **Text-to-SQL** para análise de dados de um sistema de e-commerce, powered by **Google Gemini 2.5 Flash** e **SQLite**.

Permite que usuários não técnicos façam perguntas em português natural e recebam análises completas dos dados em tempo real — sem escrever uma linha de SQL.

---

## Início Rápido

> Siga estes 4 passos para ter o agente rodando em menos de 2 minutos.

**1. Clone e instale as dependências**
```bash
git clone https://github.com/jppatriotacarvalho/E-commerce-Projeto.git
cd E-commerce-Projeto
pip install -r requirements.txt
```

**2. Coloque o banco de dados na pasta do projeto**

Copie o arquivo `banco.db` para a raiz do projeto (mesma pasta do `agent.py`).

**3. Configure sua API Key do Gemini**
```bash
cp .env.example .env
```
Abra o `.env` e substitua `sua_chave_aqui` pela sua chave do [Google AI Studio](https://aistudio.google.com/apikey):
```
GEMINI_API_KEY=AIzaSy...sua_chave_real
DB_PATH=banco.db
```

**4. Execute o agente**

Interface web no navegador (recomendado):
```bash
uvicorn api:app --reload
```
Acesse **http://localhost:8000** e comece a fazer perguntas.

Ou pelo terminal:
```bash
python agent.py
```

---

## Sumário

- [Visão Geral](#visão-geral)
- [Stack Tecnológica](#stack-tecnológica)
- [Banco de Dados](#banco-de-dados)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração da API Key](#configuração-da-api-key)
- [Como Usar](#como-usar)
  - [Opção 1 — Interface Web (recomendado)](#opção-1--interface-web-recomendado)
  - [Opção 2 — Terminal (CLI)](#opção-2--terminal-cli)
  - [Opção 3 — Jupyter Notebook](#opção-3--jupyter-notebook)
  - [Opção 4 — API REST direta](#opção-4--api-rest-direta)
- [Exemplos de Perguntas](#exemplos-de-perguntas)
- [Arquitetura e Fluxo](#arquitetura-e-fluxo)
- [Guardrails de Segurança](#guardrails-de-segurança)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## Visão Geral

O agente recebe uma pergunta em linguagem natural, gera automaticamente uma query SQL para o banco SQLite, executa a consulta e devolve uma análise textual clara e formatada.

**Fluxo:**
```
Pergunta do usuário
       ↓
  Gemini 2.5 Flash (gera SQL)
       ↓
  SQLite (executa query)
       ↓
  Gemini 2.5 Flash (analisa resultados)
       ↓
  Resposta em português
```

---

## Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| LLM | Google Gemini 2.5 Flash (`gemini-2.5-flash`) |
| SDK do Modelo | `google-genai` >= 1.0.0 |
| Banco de Dados | SQLite3 (embutido no Python) |
| Backend / API | FastAPI + Uvicorn |
| Interface Web | HTML + CSS + JS puro (sem frameworks) |
| Gráficos | Matplotlib >= 3.7 |
| Notebook | Jupyter |
| Linguagem | Python 3.10+ |
| Config | python-dotenv |

---

## Banco de Dados

O arquivo `banco.db` é um SQLite com 7 tabelas de um sistema de e-commerce:

| Tabela | Descrição | Linhas |
|---|---|---|
| `dim_consumidores` | Dados dos clientes (cidade, estado, CEP) | ~99 mil |
| `dim_produtos` | Catálogo de produtos com categorias e dimensões | ~33 mil |
| `dim_vendedores` | Cadastro de vendedores | ~3 mil |
| `fat_pedidos` | Pedidos com status, datas e métricas de entrega | ~99 mil |
| `fat_pedido_total` | Valor total pago por pedido (BRL e USD) | ~99 mil |
| `fat_itens_pedidos` | Itens individuais de cada pedido | ~113 mil |
| `fat_avaliacoes_pedidos` | Avaliações e comentários dos pedidos (1–5) | ~95 mil |

> O arquivo `banco.db` **não é incluído no repositório** por ser um arquivo binário grande. Coloque-o na raiz do projeto antes de executar.

---

## Pré-requisitos

- Python **3.10** ou superior
- Arquivo **`banco.db`** na raiz do projeto
- Conta no [Google AI Studio](https://aistudio.google.com/) para obter a **Gemini API Key** (gratuita)

---

## Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/jppatriotacarvalho/E-commerce-Projeto.git
cd E-commerce-Projeto

# 2. Crie e ative um ambiente virtual (recomendado)
python -m venv .venv

# Windows:
.venv\Scripts\activate

# Linux / macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

---

## Configuração da API Key

### 1. Obter a chave

1. Acesse [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Faça login com sua conta Google
3. Clique em **"Create API Key"**
4. Copie a chave gerada

### 2. Configurar no projeto

Copie o arquivo de exemplo e cole sua chave:

```bash
cp .env.example .env
```

Edite o `.env`:

```
GEMINI_API_KEY=AIzaSy...sua_chave_real
DB_PATH=banco.db
```

> A chave é lida automaticamente via `load_dotenv()` — não é necessário exportar variáveis de ambiente manualmente.

---

## Como Usar

Certifique-se de que o `banco.db` está na raiz do projeto e o `.env` está configurado.

---

### Opção 1 — Interface Web (recomendado)

Inicia o servidor FastAPI com interface de chat no navegador:

```bash
uvicorn api:app --reload
```

Acesse: **http://localhost:8000**

A interface oferece:
- Perguntas sugeridas em botões para todas as categorias do enunciado
- Campo de texto para perguntas livres
- Histórico de conversa estilo chat com memória de sessão
- Animação de "digitando" enquanto o agente processa
- Respostas formatadas com negrito, listas e seções

---

### Opção 2 — Terminal (CLI)

Interface interativa direto no terminal:

```bash
python agent.py
```

```
============================================================
  🛒  Agente de Análise E-Commerce
  Powered by Google Gemini 2.5 Flash + SQLite
============================================================
Digite sua pergunta em português natural.
Comandos especiais: 'sair' (encerra) | 'reset' (nova conversa)

Você: Quais são os 10 produtos mais vendidos?
```

**Comandos especiais:**

| Comando | Ação |
|---|---|
| `reset` | Limpa o histórico e inicia nova conversa |
| `sair` / `exit` / `quit` | Encerra o programa |

---

### Opção 3 — Jupyter Notebook

Ideal para exploração interativa e análises documentadas:

```bash
jupyter notebook notebook.ipynb
```

Ou com JupyterLab:

```bash
jupyter lab
```

O notebook já carrega automaticamente o `.env` via `load_dotenv()` na primeira célula. Execute as células em ordem ou use a seção **"Perguntas Livres"** para fazer suas próprias consultas.

Seções disponíveis no notebook:
1. Configuração
2. Análise de Vendas e Receita
3. Análise de Entrega e Logística
4. Análise de Satisfação e Avaliações
5. Análise de Consumidores
6. Análise de Vendedores e Produtos
7. Perguntas Livres

---

### Opção 4 — API REST direta

A API também pode ser consumida diretamente por outros sistemas.

**Documentação interativa (Swagger):** http://localhost:8000/docs

#### Endpoints

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/` | Interface web |
| `POST` | `/ask` | Envia pergunta ao agente |
| `POST` | `/session/new` | Cria nova sessão |
| `POST` | `/session/{id}/reset` | Reinicia sessão existente |
| `DELETE` | `/session/{id}` | Remove sessão da memória |
| `GET` | `/sessions` | Lista sessões ativas |

#### Exemplo com `curl`

```bash
# Criar sessão
curl -X POST http://localhost:8000/session/new

# Fazer pergunta (use o session_id retornado)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quais são os 10 produtos mais vendidos?",
    "session_id": "SEU_SESSION_ID"
  }'
```

#### Exemplo com Python

```python
import requests

# Criar sessão
session = requests.post("http://localhost:8000/session/new").json()
session_id = session["session_id"]

# Fazer perguntas
response = requests.post("http://localhost:8000/ask", json={
    "question": "Qual é a receita total por categoria de produto?",
    "session_id": session_id
})

print(response.json()["answer"])
```

---

## Exemplos de Perguntas

O agente entende perguntas em português natural. Exemplos por categoria:

### Vendas e Receita
- `Quais são os 10 produtos mais vendidos?`
- `Qual é a receita total por categoria de produto?`
- `Qual foi o mês com maior faturamento?`
- `Qual é o ticket médio dos pedidos?`
- `Qual a evolução mensal das vendas?`

### Entrega e Logística
- `Qual é a quantidade de pedidos por status?`
- `Qual o percentual de pedidos entregues no prazo por estado?`
- `Quais estados têm maior atraso médio nas entregas?`
- `Qual é o tempo médio de entrega?`

### Satisfação e Avaliações
- `Qual é a média de avaliação geral dos pedidos?`
- `Quais são os top 10 vendedores com melhor avaliação?`
- `Quais categorias têm maior taxa de avaliação negativa?`
- `Quantos pedidos têm nota 1 ou 2?`

### Consumidores
- `Quais estados têm maior volume de pedidos e maior ticket médio?`
- `Quais cidades compram mais?`
- `Qual é a distribuição de pedidos por estado?`

### Vendedores e Produtos
- `Quais produtos são mais vendidos por estado?`
- `Quais vendedores têm mais pedidos?`
- `Qual é o produto mais caro disponível?`
- `Quais vendedores têm maior receita total?`

---

## Arquitetura e Fluxo

O agente opera em múltiplos turnos de conversa com memória de sessão:

1. **Recebe** a pergunta do usuário
2. **Envia** ao Gemini 2.5 Flash com o schema completo do banco como contexto
3. **Extrai** o bloco SQL gerado pelo modelo (`\`\`\`sql ... \`\`\``)
4. **Valida** a query pelo guardrail (somente SELECT/WITH permitidos)
5. **Executa** no SQLite e coleta os resultados (máx. 200 linhas)
6. **Envia** os resultados de volta ao modelo para análise
7. **Retorna** a análise em português formatada

---

## Guardrails de Segurança

O agente possui validação de segurança antes de qualquer execução no banco:

- Apenas `SELECT` e `WITH` (CTEs) são aceitos
- Bloqueados: `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `CREATE`, `TRUNCATE`, `REPLACE`
- Validação por regex com `\b` (word boundary) para evitar falsos positivos
- Resultados truncados em 200 linhas para proteger o contexto do modelo
- Em caso de SQL inválido, o agente recebe o erro e tenta corrigir automaticamente

---

## Estrutura do Projeto

```
ecommerce-agent/
├── agent.py            # Núcleo do agente: Text-to-SQL, guardrails, CLI
├── api.py              # Backend FastAPI: endpoints REST + serve interface web
├── static/
│   └── index.html      # Interface de chat no navegador (HTML/CSS/JS puro)
├── notebook.ipynb      # Jupyter Notebook com análises por categoria
├── banco.db            # Banco SQLite (não versionado — adicionar manualmente)
├── requirements.txt    # Dependências Python
├── .env.example        # Modelo do arquivo de configuração
├── .env                # Configuração local com API Key (não versionado)
├── .gitignore          # Ignora .env, banco.db, __pycache__, etc.
└── README.md           # Este arquivo
```

---

## Licença

MIT
