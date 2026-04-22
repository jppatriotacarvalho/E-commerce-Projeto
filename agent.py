"""
E-Commerce Analytics Agent
Text-to-SQL agent powered by Google Gemini 2.5 Flash
"""

import os
import re
import sqlite3
import json
import textwrap
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", "banco.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash"  # Gemini 2.5 Flash

# ─── Database Schema ──────────────────────────────────────────────────────────

SCHEMA = """
=== BANCO DE DADOS: E-Commerce SQLite ===

Tabela: dim_consumidores
  - id_consumidor  TEXT  (chave)
  - prefixo_cep    INTEGER
  - nome_consumidor TEXT
  - cidade         TEXT
  - estado         TEXT  (ex: SP, RJ, MG)

Tabela: dim_produtos
  - id_produto     TEXT  (chave)
  - nome_produto   TEXT
  - categoria_produto TEXT
  - peso_produto_gramas REAL
  - comprimento_centimetros REAL
  - altura_centimetros REAL
  - largura_centimetros REAL

Tabela: dim_vendedores
  - id_vendedor    TEXT  (chave)
  - nome_vendedor  TEXT
  - prefixo_cep    INTEGER
  - cidade         TEXT
  - estado         TEXT

Tabela: fat_pedidos
  - id_pedido      TEXT  (chave)
  - id_consumidor  TEXT
  - status         TEXT  (ex: entregue, cancelado, processando, enviado)
  - pedido_compra_timestamp TEXT
  - pedido_entregue_timestamp TEXT
  - data_estimada_entrega TEXT
  - tempo_entrega_dias REAL
  - tempo_entrega_estimado_dias INTEGER
  - diferenca_entrega_dias REAL  (negativo = adiantado, positivo = atrasado)
  - entrega_no_prazo TEXT  ('Sim', 'Não' ou 'Não Entregue')

Tabela: fat_pedido_total
  - id_pedido      TEXT  (chave)
  - id_consumidor  TEXT
  - status         TEXT
  - valor_total_pago_brl REAL
  - valor_total_pago_usd REAL
  - data_pedido    TEXT

Tabela: fat_itens_pedidos
  - id_pedido      TEXT
  - id_item        INTEGER
  - id_produto     TEXT
  - id_vendedor    TEXT
  - preco_BRL      REAL
  - preco_frete    REAL

Tabela: fat_avaliacoes_pedidos
  - id_avaliacao   TEXT  (chave)
  - id_pedido      TEXT
  - avaliacao      INTEGER  (1 a 5)
  - titulo_comentario TEXT
  - comentario     TEXT
  - data_comentario TEXT
  - data_resposta  TEXT

=== RELACIONAMENTOS ===
fat_itens_pedidos.id_pedido      → fat_pedidos.id_pedido
fat_itens_pedidos.id_produto     → dim_produtos.id_produto
fat_itens_pedidos.id_vendedor    → dim_vendedores.id_vendedor
fat_pedidos.id_consumidor        → dim_consumidores.id_consumidor
fat_pedido_total.id_pedido       → fat_pedidos.id_pedido
fat_avaliacoes_pedidos.id_pedido → fat_pedidos.id_pedido
"""

# ─── Guardrails ────────────────────────────────────────────────────────────────

BLOCKED_KEYWORDS = ["drop", "delete", "insert", "update", "alter", "create", "truncate", "replace"]

def is_safe_query(sql: str) -> tuple[bool, str]:
    """Verifica se o SQL é apenas leitura (SELECT)."""
    cleaned = sql.strip().lower()
    for kw in BLOCKED_KEYWORDS:
        pattern = rf"\b{kw}\b"
        if re.search(pattern, cleaned):
            return False, f"Operação '{kw.upper()}' não é permitida. Apenas consultas de leitura (SELECT) são aceitas."
    if not cleaned.startswith("select") and not cleaned.startswith("with"):
        return False, "Apenas instruções SELECT ou WITH (CTE) são permitidas."
    return True, ""

# ─── Database Layer ────────────────────────────────────────────────────────────

def run_query(sql: str) -> tuple[list[dict], str | None]:
    """Executa uma query SQLite e retorna (rows, error)."""
    safe, reason = is_safe_query(sql)
    if not safe:
        return [], reason
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows, None
    except sqlite3.Error as e:
        return [], f"Erro no banco de dados: {e}"

# ─── Gemini Agent ──────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    return f"""Você é um agente especialista em análise de dados de E-Commerce.
Seu papel é ajudar usuários não técnicos a consultar e entender dados de uma loja virtual.

SCHEMA DO BANCO DE DADOS:
{SCHEMA}

REGRAS IMPORTANTES:
1. Quando o usuário fizer uma pergunta sobre dados, gere uma query SQL válida para SQLite.
2. Use APENAS instruções SELECT. Nunca use DROP, DELETE, INSERT, UPDATE, etc.
3. Ao gerar SQL, coloque-o dentro de um bloco de código markdown: ```sql ... ```
4. Após receber os resultados da query, forneça uma análise clara e em português brasileiro.
5. Se a pergunta não for sobre os dados do banco, responda normalmente.
6. Seja direto, objetivo e use formatação clara nas respostas.
7. Quando os dados tiverem muitas linhas, destaque os pontos mais importantes.
8. Nunca exponha IDs internos como resultado principal — prefira nomes legíveis.
9. Use alias nas colunas SQL para nomes mais legíveis (ex: AS "Total de Pedidos").
10. Para análises financeiras, formate valores monetários em BRL.
"""

def extract_sql(text: str) -> str | None:
    """Extrai bloco SQL do texto do modelo."""
    match = re.search(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # fallback: buscar SELECT solto
    match2 = re.search(r"((?:WITH|SELECT)\s.+?)(?:\n\n|$)", text, re.DOTALL | re.IGNORECASE)
    if match2:
        return match2.group(1).strip()
    return None

class EcommerceAgent:
    def __init__(self, api_key: str | None = None):
        key = api_key or GEMINI_API_KEY
        if not key:
            raise ValueError(
                "GEMINI_API_KEY não encontrada. "
                "Defina a variável de ambiente GEMINI_API_KEY ou passe api_key ao instanciar."
            )
        self._client = genai.Client(api_key=key)
        self._config = types.GenerateContentConfig(
            system_instruction=build_system_prompt(),
        )
        self.chat = self._client.chats.create(model=MODEL_NAME, config=self._config)
        self._turn = 0

    def _format_results(self, rows: list[dict]) -> str:
        """Formata os resultados da query para envio ao modelo."""
        if not rows:
            return "A query não retornou resultados."
        # Limitar a 200 linhas para não explodir o contexto
        truncated = len(rows) > 200
        sample = rows[:200]
        result_str = json.dumps(sample, ensure_ascii=False, default=str, indent=2)
        if truncated:
            result_str += f"\n\n[... truncado: exibindo 200 de {len(rows)} linhas]"
        return result_str

    def ask(self, question: str) -> str:
        """Processa uma pergunta do usuário e retorna a resposta do agente."""
        self._turn += 1
        print(f"\n{'='*60}")
        print(f"[Turno {self._turn}] Usuário: {question}")
        print('='*60)

        # Primeira mensagem ao modelo
        response = self.chat.send_message(question)
        assistant_text = response.text

        # Verificar se há SQL para executar
        sql = extract_sql(assistant_text)
        if sql:
            print(f"\n[SQL Gerado]\n{sql}\n")
            rows, error = run_query(sql)

            if error:
                print(f"[Erro] {error}")
                followup = f"Ocorreu um erro ao executar a query: {error}\nPor favor, revise o SQL e forneça uma resposta alternativa ou explique o problema."
                response2 = self.chat.send_message(followup)
                return response2.text

            print(f"[Resultados] {len(rows)} linha(s) retornada(s)")

            # Enviar resultados de volta ao modelo para análise
            data_str = self._format_results(rows)
            analysis_prompt = (
                f"Aqui estão os resultados da query SQL:\n\n{data_str}\n\n"
                f"Com base nesses dados, forneça uma análise clara e objetiva em português "
                f"brasileiro respondendo à pergunta original do usuário. "
                f"Destaque os pontos mais relevantes e use formatação legível."
            )
            response3 = self.chat.send_message(analysis_prompt)
            return response3.text

        return assistant_text

    def reset(self):
        """Reinicia o histórico de conversa."""
        self.chat = self._client.chats.create(model=MODEL_NAME, config=self._config)
        self._turn = 0
        print("[Agente] Conversa reiniciada.")


# ─── CLI Interface ─────────────────────────────────────────────────────────────

def run_cli():
    """Interface de linha de comando para o agente."""
    print("\n" + "="*60)
    print("  🛒  Agente de Análise E-Commerce")
    print("  Powered by Google Gemini 2.5 Flash + SQLite")
    print("="*60)
    print("Digite sua pergunta em português natural.")
    print("Comandos especiais: 'sair' (encerra) | 'reset' (nova conversa)\n")

    agent = EcommerceAgent()

    while True:
        try:
            question = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Encerrando agente]")
            break

        if not question:
            continue
        if question.lower() in ("sair", "exit", "quit"):
            print("Até logo!")
            break
        if question.lower() == "reset":
            agent.reset()
            continue

        answer = agent.ask(question)
        print(f"\nAgente:\n{textwrap.fill(answer, width=80) if len(answer) < 500 else answer}\n")


if __name__ == "__main__":
    run_cli()
