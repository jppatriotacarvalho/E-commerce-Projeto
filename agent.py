"""
E-Commerce Analytics Agent
Text-to-SQL agent powered by Google Gemini 2.5 Flash
"""

import os
import re
import sqlite3
import json
import textwrap
import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", "banco.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash"

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
    cleaned = sql.strip().lower()
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", cleaned):
            return False, f"Operação '{kw.upper()}' não é permitida. Apenas consultas de leitura (SELECT) são aceitas."
    if not cleaned.startswith("select") and not cleaned.startswith("with"):
        return False, "Apenas instruções SELECT ou WITH (CTE) são permitidas."
    return True, ""

# ─── Anonymization ────────────────────────────────────────────────────────────

_ANON_COLS = {"nome_consumidor", "nome_vendedor"}

def anonymize_rows(rows: list[dict]) -> tuple[list[dict], bool]:
    """Substitui colunas sensíveis por valores anônimos. Retorna (rows, foi_anonimizado)."""
    if not rows:
        return rows, False
    sensitive = [k for k in rows[0] if k.lower() in _ANON_COLS]
    if not sensitive:
        return rows, False
    result = []
    for i, row in enumerate(rows):
        new_row = dict(row)
        for col in sensitive:
            prefix = "Cliente" if "consumidor" in col.lower() else "Vendedor"
            new_row[col] = f"{prefix} #{i + 1:04d}"
        result.append(new_row)
    return result, True

# ─── Chart Generation ─────────────────────────────────────────────────────────

_BG = "#111118"
_ACCENT = "#6366f1"
_TEXT = "#e2e8f0"
_MUTED = "#94a3b8"
_GRID = "#1e1e2e"
_SPINE = "#2a2d3e"

def _apply_dark_style(fig, ax):
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.tick_params(colors=_MUTED, labelsize=11)
    for spine in ax.spines.values():
        spine.set_color(_SPINE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, color=_GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)

def _fmt_value(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:,.1f}" if v != int(v) else f"{int(v):,}"


def try_generate_chart(rows: list[dict]) -> str | None:
    """Gera gráfico a partir dos resultados. Retorna base64 PNG ou None."""
    if not rows or len(rows) < 2:
        return None

    cols = list(rows[0].keys())
    if len(cols) < 2:
        return None

    label_col = cols[0]
    value_col = None
    for col in cols[1:]:
        try:
            float(rows[0][col])
            value_col = col
            break
        except (TypeError, ValueError):
            continue

    if value_col is None:
        return None

    # Limitar a 20 itens para legibilidade
    display_rows = rows[:20]
    truncated = len(rows) > 20

    labels = [str(r[label_col])[:18] for r in display_rows]
    try:
        values = [float(r[value_col]) for r in display_rows]
    except (TypeError, ValueError):
        return None

    n = len(labels)
    is_time = any(kw in label_col.lower() for kw in ["data", "mes", "mês", "ano", "month", "year"])

    fig_w = max(11, min(n * 0.8, 18))
    fig, ax = plt.subplots(figsize=(fig_w, 6))
    _apply_dark_style(fig, ax)

    title = value_col
    if truncated:
        title += f" (top 20 de {len(rows)})"

    if is_time:
        ax.plot(range(n), values, color=_ACCENT, linewidth=2.5, marker="o", markersize=6, zorder=3)
        ax.fill_between(range(n), values, alpha=0.12, color=_ACCENT)
        ax.set_xticks(range(n))
        ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=11)
    else:
        bars = ax.bar(range(n), values, color=_ACCENT, alpha=0.85,
                      edgecolor="#4338ca", linewidth=0.5, zorder=3, width=0.65)
        # Mostrar labels só quando couber (≤ 15 barras)
        if n <= 15:
            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(values) * 0.012,
                    _fmt_value(val),
                    ha="center", va="bottom", fontsize=9, color=_TEXT,
                )
        ax.set_xticks(range(n))
        rot = 45 if n > 8 else 30
        ax.set_xticklabels(labels, rotation=rot, ha="right", fontsize=max(9, 12 - n // 5))

    ax.set_title(title, color=_TEXT, fontsize=14, pad=14)
    ax.set_xlabel(label_col, color=_MUTED, fontsize=11, labelpad=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: _fmt_value(x)))
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

# ─── Database Layer ────────────────────────────────────────────────────────────

def run_query(sql: str) -> tuple[list[dict], str | None]:
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
    match = re.search(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
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
        if not rows:
            return "A query não retornou resultados."
        truncated = len(rows) > 200
        sample = rows[:200]
        result_str = json.dumps(sample, ensure_ascii=False, default=str, indent=2)
        if truncated:
            result_str += f"\n\n[... truncado: exibindo 200 de {len(rows)} linhas]"
        return result_str

    def ask(self, question: str) -> dict:
        """Processa uma pergunta e retorna dict com answer, chart (base64|None) e anonymized (bool)."""
        self._turn += 1
        print(f"\n{'='*60}")
        print(f"[Turno {self._turn}] Usuário: {question}")
        print("=" * 60)

        response = self.chat.send_message(question)
        assistant_text = response.text

        sql = extract_sql(assistant_text)
        if sql:
            print(f"\n[SQL Gerado]\n{sql}\n")
            rows, error = run_query(sql)

            if error:
                print(f"[Erro] {error}")
                response2 = self.chat.send_message(
                    f"Ocorreu um erro ao executar a query: {error}\n"
                    "Por favor, revise o SQL e forneça uma resposta alternativa."
                )
                return {"answer": response2.text, "chart": None, "anonymized": False}

            print(f"[Resultados] {len(rows)} linha(s) retornada(s)")

            rows_anon, was_anonymized = anonymize_rows(rows)
            if was_anonymized:
                print("[Anonimização] Dados pessoais substituídos.")

            chart_b64 = try_generate_chart(rows_anon)
            if chart_b64:
                print("[Gráfico] Gerado com sucesso.")

            data_str = self._format_results(rows_anon)
            analysis_prompt = (
                f"Aqui estão os resultados da query SQL:\n\n{data_str}\n\n"
                f"Com base nesses dados, forneça uma análise clara e objetiva em português "
                f"brasileiro respondendo à pergunta original do usuário. "
                f"Destaque os pontos mais relevantes e use formatação legível."
            )
            response3 = self.chat.send_message(analysis_prompt)
            return {
                "answer": response3.text,
                "chart": chart_b64,
                "anonymized": was_anonymized,
            }

        return {"answer": assistant_text, "chart": None, "anonymized": False}

    def reset(self):
        self.chat = self._client.chats.create(model=MODEL_NAME, config=self._config)
        self._turn = 0
        print("[Agente] Conversa reiniciada.")


# ─── CLI Interface ─────────────────────────────────────────────────────────────

def run_cli():
    print("\n" + "=" * 60)
    print("  🛒  Agente de Análise E-Commerce")
    print("  Powered by Google Gemini 2.5 Flash + SQLite")
    print("=" * 60)
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

        result = agent.ask(question)
        answer = result["answer"]
        print(f"\nAgente:\n{textwrap.fill(answer, width=80) if len(answer) < 500 else answer}")
        if result["anonymized"]:
            print("\n[🔒 Dados pessoais anonimizados]")
        if result["chart"]:
            print("[📊 Gráfico disponível na interface web]")
        print()


if __name__ == "__main__":
    run_cli()
