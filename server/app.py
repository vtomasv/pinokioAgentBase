"""
Servidor principal del plugin Brand Structure.
Orquesta dos agentes LLM:
  1. Entrevistador: realiza preguntas sobre la marca
  2. Generador: crea el documento de estructura de marca corporativa
"""
import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel
import uvicorn
import requests

# ─── Configuración ────────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 8000))
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
PLUGIN_DIR = Path(os.environ.get("PLUGIN_DIR", "."))
OLLAMA_URL = "http://localhost:11434"

app = FastAPI(title="Brand Structure Plugin API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Modelos de datos ─────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    session_id: str
    message: str

class SessionCreate(BaseModel):
    company_name: str

# ─── Utilidades ───────────────────────────────────────────────────────────────

def load_agents() -> list:
    agents_file = DATA_DIR / "agents" / "agents.json"
    if agents_file.exists():
        return json.loads(agents_file.read_text(encoding="utf-8"))
    defaults_file = PLUGIN_DIR / "defaults" / "agents.json"
    if defaults_file.exists():
        return json.loads(defaults_file.read_text(encoding="utf-8"))
    return []

def get_agent(agent_id: str) -> Optional[dict]:
    return next((a for a in load_agents() if a["id"] == agent_id), None)

def get_system_prompt(agent_id: str) -> str:
    prompt_file = DATA_DIR / "prompts" / "system" / f"{agent_id}.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    agent = get_agent(agent_id)
    return agent.get("systemPrompt", "") if agent else ""

def call_ollama(model: str, messages: list, temperature: float = 0.7,
                max_tokens: int = 2048) -> str:
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "options": {"temperature": temperature, "num_predict": max_tokens},
                "stream": False,
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="El modelo tardó demasiado. Intenta de nuevo.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al llamar a Ollama: {str(e)}")

# ─── Gestión de Sesiones ──────────────────────────────────────────────────────

def get_session(session_id: str) -> dict:
    session_file = DATA_DIR / "sessions" / session_id / "session.json"
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return json.loads(session_file.read_text(encoding="utf-8"))

def save_session(session_id: str, session_data: dict):
    session_dir = DATA_DIR / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    session_data["updatedAt"] = datetime.now().isoformat()
    (session_dir / "session.json").write_text(
        json.dumps(session_data, indent=2, ensure_ascii=False)
    )

def append_message(session_id: str, role: str, content: str, agent_id: str = None):
    session = get_session(session_id)
    message = {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
    if agent_id:
        message["agent_id"] = agent_id
    session.setdefault("messages", []).append(message)
    save_session(session_id, session)

def get_interview_messages(session_id: str) -> list:
    session = get_session(session_id)
    messages = []
    system_prompt = get_system_prompt("interviewer")
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in session.get("messages", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    return messages

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse(url="/ui/index.html")

@app.post("/api/sessions")
async def create_session(body: SessionCreate):
    session_id = str(uuid.uuid4())[:8]
    session_data = {
        "id": session_id,
        "companyName": body.company_name,
        "status": "interviewing",
        "messages": [],
        "document": None,
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
    }
    save_session(session_id, session_data)

    agent = get_agent("interviewer")
    system_prompt = get_system_prompt("interviewer")

    opening_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Hola, quiero crear el documento de estructura de marca para mi empresa "
            f"llamada '{body.company_name}'. Por favor, comienza la entrevista."
        )},
    ]

    opening = call_ollama(
        model=agent["model"],
        messages=opening_messages,
        temperature=agent.get("temperature", 0.6),
        max_tokens=agent.get("maxTokens", 1024),
    )

    append_message(session_id, "user",
        f"Hola, quiero crear el documento de estructura de marca para mi empresa llamada '{body.company_name}'. Por favor, comienza la entrevista.")
    append_message(session_id, "assistant", opening, agent_id="interviewer")

    return {"session_id": session_id, "opening_message": opening, "status": "interviewing"}

@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, body: ChatMessage):
    session = get_session(session_id)
    if session["status"] != "interviewing":
        raise HTTPException(status_code=400, detail="La sesión no está en modo entrevista")

    append_message(session_id, "user", body.message)

    agent = get_agent("interviewer")
    messages = get_interview_messages(session_id)

    response = call_ollama(
        model=agent["model"],
        messages=messages,
        temperature=agent.get("temperature", 0.6),
        max_tokens=agent.get("maxTokens", 1024),
    )

    append_message(session_id, "assistant", response, agent_id="interviewer")

    session = get_session(session_id)
    interview_complete = _detect_interview_complete(response, session)

    return {
        "response": response,
        "agent": "interviewer",
        "interview_complete": interview_complete,
        "session_id": session_id,
    }

@app.post("/api/sessions/{session_id}/generate")
async def generate_document(session_id: str):
    session = get_session(session_id)

    session["status"] = "generating"
    save_session(session_id, session)

    interview_summary = _build_interview_summary(session)

    agent = get_agent("document_generator")
    system_prompt = get_system_prompt("document_generator")

    generator_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Basándote en la siguiente información recopilada sobre la empresa "
            f"'{session['companyName']}', crea el documento completo de Estructura "
            f"de Marca Corporativa:\n\n{interview_summary}"
        )},
    ]

    document = call_ollama(
        model=agent["model"],
        messages=generator_messages,
        temperature=agent.get("temperature", 0.5),
        max_tokens=agent.get("maxTokens", 4096),
    )

    session["document"] = document
    session["status"] = "completed"
    save_session(session_id, session)

    company_slug = session["companyName"].replace(" ", "_")
    doc_file = DATA_DIR / "exports" / f"marca_{session_id}_{company_slug}.md"
    doc_file.parent.mkdir(parents=True, exist_ok=True)
    doc_file.write_text(document, encoding="utf-8")

    return {"document": document, "session_id": session_id, "status": "completed"}

@app.get("/api/sessions/{session_id}")
async def get_session_info(session_id: str):
    return get_session(session_id)

@app.get("/api/sessions")
async def list_sessions():
    sessions_dir = DATA_DIR / "sessions"
    sessions = []
    if sessions_dir.exists():
        for session_dir in sorted(sessions_dir.iterdir(), reverse=True):
            session_file = session_dir / "session.json"
            if session_file.exists():
                data = json.loads(session_file.read_text(encoding="utf-8"))
                sessions.append({
                    "id": data["id"],
                    "companyName": data.get("companyName", "Sin nombre"),
                    "status": data.get("status", "unknown"),
                    "createdAt": data.get("createdAt", ""),
                    "messageCount": len(data.get("messages", [])),
                })
    return {"sessions": sessions[:20]}

@app.get("/api/sessions/{session_id}/download")
async def download_document(session_id: str):
    session = get_session(session_id)
    if not session.get("document"):
        raise HTTPException(status_code=404, detail="Documento no generado aún")
    company_slug = session.get("companyName", "empresa").replace(" ", "_")
    doc_file = DATA_DIR / "exports" / f"marca_{session_id}_{company_slug}.md"
    if not doc_file.exists():
        doc_file.write_text(session["document"], encoding="utf-8")
    return FileResponse(
        path=str(doc_file),
        media_type="text/markdown",
        filename=f"estructura_marca_{company_slug}.md",
    )

@app.get("/api/models")
async def list_models():
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in response.json().get("models", [])]
        return {"models": models}
    except Exception:
        return {"models": []}

@app.get("/api/health")
async def health():
    ollama_ok = False
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
    except Exception:
        pass
    return {"status": "ok", "ollama": ollama_ok}

# ─── Funciones auxiliares ─────────────────────────────────────────────────────

def _detect_interview_complete(response: str, session: dict) -> bool:
    messages = session.get("messages", [])
    user_messages = [m for m in messages if m["role"] == "user"]
    if len(user_messages) < 6:
        return False
    closing_phrases = [
        "ya tengo suficiente información",
        "tengo toda la información",
        "hemos completado la entrevista",
        "con esta información puedo",
        "ya podemos generar",
        "listo para generar",
        "información recopilada",
        "resumen de lo que hemos",
        "a continuación el resumen",
        "con estos datos podemos",
        "podemos proceder a generar",
        "estamos listos para crear",
    ]
    response_lower = response.lower()
    return any(phrase in response_lower for phrase in closing_phrases)

def _build_interview_summary(session: dict) -> str:
    messages = session.get("messages", [])
    lines = [f"# Información recopilada sobre: {session.get('companyName', 'la empresa')}\n"]
    for msg in messages:
        if msg["role"] == "user":
            lines.append(f"**Respuesta del cliente:** {msg['content']}")
        elif msg["role"] == "assistant":
            lines.append(f"**Pregunta del entrevistador:** {msg['content']}")
        lines.append("")
    return "\n".join(lines)

# ─── Archivos estáticos ───────────────────────────────────────────────────────

app.mount("/ui", StaticFiles(directory=str(PLUGIN_DIR / "app"), html=True), name="ui")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
