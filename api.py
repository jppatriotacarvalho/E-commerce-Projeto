"""
FastAPI Backend para o Agente de Análise E-Commerce
Executa com: uvicorn api:app --reload
"""

import os
import uuid
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

# Armazena sessões de conversa em memória
_sessions: dict[str, EcommerceAgent] = {}


def get_or_create_session(session_id: str) -> EcommerceAgent:
    if session_id not in _sessions:
        _sessions[session_id] = EcommerceAgent()
    return _sessions[session_id]


# ─── Schemas ──────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    session_id: str
    question: str
    answer: str

class SessionResponse(BaseModel):
    session_id: str
    message: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return FileResponse("static/index.html")


@app.post("/ask", response_model=QueryResponse, tags=["Agent"])
def ask(request: QueryRequest):
    """
    Envia uma pergunta ao agente em linguagem natural.
    O agente gera SQL, executa no banco e retorna a análise.
    
    - **question**: Pergunta em português (ex: "Quais são os 10 produtos mais vendidos?")
    - **session_id**: (Opcional) ID de sessão para manter contexto entre perguntas. 
                      Se omitido, uma nova sessão é criada.
    """
    session_id = request.session_id or str(uuid.uuid4())
    try:
        agent = get_or_create_session(session_id)
        answer = agent.ask(request.question)
        return QueryResponse(
            session_id=session_id,
            question=request.question,
            answer=answer,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/new", response_model=SessionResponse, tags=["Session"])
def new_session():
    """Cria uma nova sessão de conversa e retorna o session_id."""
    session_id = str(uuid.uuid4())
    _sessions[session_id] = EcommerceAgent()
    return SessionResponse(session_id=session_id, message="Sessão criada com sucesso.")


@app.post("/session/{session_id}/reset", response_model=SessionResponse, tags=["Session"])
def reset_session(session_id: str):
    """Reinicia o histórico de conversa de uma sessão existente."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    _sessions[session_id].reset()
    return SessionResponse(session_id=session_id, message="Sessão reiniciada com sucesso.")


@app.delete("/session/{session_id}", response_model=SessionResponse, tags=["Session"])
def delete_session(session_id: str):
    """Remove uma sessão da memória."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    del _sessions[session_id]
    return SessionResponse(session_id=session_id, message="Sessão removida.")


@app.get("/sessions", tags=["Session"])
def list_sessions():
    """Lista todas as sessões ativas."""
    return {"active_sessions": list(_sessions.keys()), "count": len(_sessions)}
