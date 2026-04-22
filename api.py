"""
FastAPI Backend para o Agente de Análise E-Commerce
Executa com: uvicorn api:app --reload
"""

import os
import uuid
import json
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import EcommerceAgent

app = FastAPI(
    title="E-Commerce Analytics Agent API",
    description="Text-to-SQL agent powered by Gemini 2.5 Flash para análise de dados de e-commerce.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

_sessions: dict[str, EcommerceAgent] = {}
FEEDBACK_FILE = Path("feedback.json")


def get_or_create_session(session_id: str) -> EcommerceAgent:
    if session_id not in _sessions:
        _sessions[session_id] = EcommerceAgent()
    return _sessions[session_id]


def save_feedback(entry: dict):
    data = []
    if FEEDBACK_FILE.exists():
        try:
            data = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = []
    data.append(entry)
    FEEDBACK_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    chart: Optional[str] = None
    anonymized: bool = False

class SessionResponse(BaseModel):
    session_id: str
    message: str

class FeedbackRequest(BaseModel):
    session_id: str
    question: str
    answer: str
    rating: int  # 1 = positivo, -1 = negativo


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return FileResponse("static/index.html")


@app.post("/ask", response_model=QueryResponse, tags=["Agent"])
def ask(request: QueryRequest):
    """
    Envia uma pergunta ao agente em linguagem natural.
    O agente gera SQL, executa no banco e retorna análise + gráfico (se aplicável).
    """
    session_id = request.session_id or str(uuid.uuid4())
    try:
        agent = get_or_create_session(session_id)
        result = agent.ask(request.question)
        return QueryResponse(
            session_id=session_id,
            question=request.question,
            answer=result["answer"],
            chart=result.get("chart"),
            anonymized=result.get("anonymized", False),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback", tags=["Feedback"])
def feedback(request: FeedbackRequest):
    """Registra avaliação (👍 ou 👎) de uma resposta do agente."""
    label = "positivo" if request.rating == 1 else "negativo"
    save_feedback({
        "session_id": request.session_id,
        "question": request.question,
        "rating": label,
    })
    return {"message": f"Feedback {label} registrado."}


@app.get("/feedback", tags=["Feedback"])
def get_feedback():
    """Lista todos os feedbacks registrados."""
    if not FEEDBACK_FILE.exists():
        return {"feedbacks": [], "total": 0}
    try:
        data = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = []
    positivos = sum(1 for f in data if f.get("rating") == "positivo")
    negativos = sum(1 for f in data if f.get("rating") == "negativo")
    return {"feedbacks": data, "total": len(data), "positivos": positivos, "negativos": negativos}


@app.post("/session/new", response_model=SessionResponse, tags=["Session"])
def new_session():
    session_id = str(uuid.uuid4())
    _sessions[session_id] = EcommerceAgent()
    return SessionResponse(session_id=session_id, message="Sessão criada com sucesso.")


@app.post("/session/{session_id}/reset", response_model=SessionResponse, tags=["Session"])
def reset_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    _sessions[session_id].reset()
    return SessionResponse(session_id=session_id, message="Sessão reiniciada com sucesso.")


@app.delete("/session/{session_id}", response_model=SessionResponse, tags=["Session"])
def delete_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    del _sessions[session_id]
    return SessionResponse(session_id=session_id, message="Sessão removida.")


@app.get("/sessions", tags=["Session"])
def list_sessions():
    return {"active_sessions": list(_sessions.keys()), "count": len(_sessions)}
