"""
Servidor principal del plugin Brand Structure.
Orquesta dos agentes LLM:
  1. Entrevistador: realiza preguntas sobre la marca
  2. Generador: crea el documento de estructura de marca corporativa
"""
import os
import sys
import json
import uuid
import logging
import shutil
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

# --- Logging ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# --- Configuracion ------------------------------------------------------------
PORT = int(os.environ.get("PORT", 8000))

# PLUGIN_DIR: directorio raiz del plugin
# Cuando Pinokio lanza con "path": "{{cwd}}", PLUGIN_DIR viene por env var.
# Si no viene por env, se usa el directorio padre de este archivo (server/).
_server_dir = Path(__file__).parent.resolve()
_default_plugin_dir = _server_dir.parent

PLUGIN_DIR = Path(os.environ.get("PLUGIN_DIR", str(_default_plugin_dir))).resolve()
DATA_DIR = Path(os.environ.get("DATA_DIR", str(PLUGIN_DIR / "data"))).resolve()
OLLAMA_URL = "http://localhost:11434"

log.info(f"PLUGIN_DIR: {PLUGIN_DIR}")
log.info(f"DATA_DIR:   {DATA_DIR}")
log.info(f"PORT:       {PORT}")

# Crear directorios necesarios
for d in ["agents", "sessions", "exports", "prompts"]:
    (DATA_DIR / d).mkdir(parents=True, exist_ok=True)

# Copiar defaults si no existen los datos
_defaults_agents = PLUGIN_DIR / "defaults" / "agents.json"
_data_agents = DATA_DIR / "agents" / "agents.json"
if _defaults_agents.exists() and not _data_agents.exists():
    shutil.copy(_defaults_agents, _data_agents)
    log.info("Copiado defaults/agents.json -> data/agents/agents.json")

_defaults_prompts = PLUGIN_DIR / "defaults" / "prompts"
_data_prompts = DATA_DIR / "prompts"
if _defaults_prompts.exists():
    for f in _defaults_prompts.iterdir():
        dest = _data_prompts / f.name
        if not dest.exists():
            shutil.copy(f, dest)
            log.info(f"Copiado prompt: {f.name}")

# --- App FastAPI --------------------------------------------------------------
app = FastAPI(title="Brand Structure Plugin API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modelos de datos ---------------------------------------------------------
class ChatMessage(BaseModel):
    session_id: str
    message: str

class SessionCreate(BaseModel):
    company_name: str

# --- Utilidades ---------------------------------------------------------------
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
    # Buscar en data/prompts/<agent_id>.md
    prompt_file = DATA_DIR / "prompts" / f"{agent_id}.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    # Buscar en defaults/prompts/<agent_id>.md
    defaults_prompt = PLUGIN_DIR / "defaults" / "prompts" / f"{agent_id}.md"
    if defaults_prompt.exists():
        return defaults_prompt.read_text(encoding="utf-8")
    # Fallback al systemPrompt del agente
    agent = get_agent(agent_id)
    return agent.get("systemPrompt", "") if agent else ""

def call_ollama(model: str, messages: list, temperature: float = 0.7,
                max_tokens: int = 2048) -> str:
    try:
        log.info(f"Llamando Ollama: model={model}, msgs={len(messages)}")
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "options": {"temperature": temperature, "num_predict": max_tokens},
                "stream": False,
            },
            timeout=300,
        )
        response.raise_for_status()
        result = response.json()["message"]["content"]
        log.info(f"Ollama respondio: {len(result)} chars")
        return result
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="El modelo tardo demasiado. Intenta de nuevo.")
    except Exception as e:
        log.error(f"Error Ollama: {e}")
        raise HTTPException(status_code=500, detail=f"Error al llamar a Ollama: {str(e)}")

# --- Gestion de Sesiones ------------------------------------------------------
def get_session(session_id: str) -> dict:
    session_file = DATA_DIR / "sessions" / session_id / "session.json"
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    return json.loads(session_file.read_text(encoding="utf-8"))

def save_session(session_id: str, session_data: dict):
    session_dir = DATA_DIR / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    session_data["updatedAt"] = datetime.now().isoformat()
    (session_dir / "session.json").write_text(
        json.dumps(session_data, indent=2, ensure_ascii=False)
    )

def get_interview_messages(session_id: str) -> list:
    session = get_session(session_id)
    messages = []
    system_prompt = get_system_prompt("interviewer")
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in session.get("messages", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    return messages

# --- Endpoints ----------------------------------------------------------------
@app.get("/")
async def root():
    return RedirectResponse(url="/ui/index.html")

@app.get("/api/health")
async def health():
    ollama_ok = False
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
    except Exception:
        pass
    return {
        "status": "ok",
        "ollama": ollama_ok,
        "plugin_dir": str(PLUGIN_DIR),
        "data_dir": str(DATA_DIR),
        "port": PORT,
    }

@app.post("/api/sessions")
async def create_session(body: SessionCreate):
    session_id = str(uuid.uuid4())[:8]
    agent = get_agent("interviewer")
    model = agent["model"] if agent else "llama3.1:8b"

    session_data = {
        "id": session_id,
        "companyName": body.company_name,
        "status": "interviewing",
        "model": model,
        "messages": [],
        "document": None,
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
    }
    save_session(session_id, session_data)

    system_prompt = get_system_prompt("interviewer")
    opening_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Hola, quiero crear el documento de estructura de marca para mi empresa "
            f"llamada '{body.company_name}'. Por favor, comienza la entrevista."
        )},
    ]

    opening = call_ollama(
        model=model,
        messages=opening_messages,
        temperature=agent.get("temperature", 0.6) if agent else 0.6,
        max_tokens=agent.get("maxTokens", 1024) if agent else 1024,
    )

    session_data = get_session(session_id)
    session_data["messages"].append({
        "role": "user",
        "content": f"Hola, quiero crear el documento de estructura de marca para mi empresa llamada '{body.company_name}'. Por favor, comienza la entrevista.",
        "timestamp": datetime.now().isoformat(),
    })
    session_data["messages"].append({
        "role": "assistant",
        "content": opening,
        "agent_id": "interviewer",
        "timestamp": datetime.now().isoformat(),
    })
    save_session(session_id, session_data)

    log.info(f"Sesion creada: {session_id} para '{body.company_name}'")
    return {"session_id": session_id, "opening_message": opening, "status": "interviewing"}

@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, body: ChatMessage):
    session = get_session(session_id)
    if session.get("status") == "completed":
        raise HTTPException(status_code=400, detail="La sesion ya fue completada")

    # Guardar mensaje del usuario
    session.setdefault("messages", []).append({
        "role": "user",
        "content": body.message,
        "timestamp": datetime.now().isoformat(),
    })
    save_session(session_id, session)

    # Construir historial para el agente entrevistador
    messages = get_interview_messages(session_id)
    agent = get_agent("interviewer")
    model = agent["model"] if agent else "llama3.1:8b"
    temperature = agent.get("temperature", 0.7) if agent else 0.7
    max_tokens = agent.get("maxTokens", 1024) if agent else 1024

    response_text = call_ollama(model, messages, temperature, max_tokens)

    # Guardar respuesta del asistente
    session = get_session(session_id)
    session["messages"].append({
        "role": "assistant",
        "content": response_text,
        "agent_id": "interviewer",
        "timestamp": datetime.now().isoformat(),
    })

    # Detectar si la entrevista esta completa
    interview_done = _detect_interview_complete(response_text, session)
    if interview_done:
        session["status"] = "ready_to_generate"

    save_session(session_id, session)
    return {
        "response": response_text,
        "agent": "interviewer",
        "session_id": session_id,
        "status": session["status"],
        "interview_complete": interview_done,
    }

@app.post("/api/sessions/{session_id}/generate")
async def generate_document(session_id: str):
    session = get_session(session_id)
    session["status"] = "generating"
    save_session(session_id, session)

    interview_summary = _build_interview_summary(session)
    agent = get_agent("document_generator")
    model = agent["model"] if agent else "llama3.1:8b"
    temperature = agent.get("temperature", 0.5) if agent else 0.5
    max_tokens = agent.get("maxTokens", 4096) if agent else 4096
    system_prompt = get_system_prompt("document_generator")

    generator_messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Basandote en la siguiente informacion recopilada sobre la empresa "
                f"'{session['companyName']}', crea el documento completo de Estructura "
                f"de Marca Corporativa:\n\n{interview_summary}"
            ),
        },
    ]

    document = call_ollama(model, generator_messages, temperature, max_tokens)
    session["document"] = document
    session["status"] = "completed"
    save_session(session_id, session)

    company_slug = session["companyName"].replace(" ", "_")
    doc_file = DATA_DIR / "exports" / f"marca_{session_id}_{company_slug}.md"
    doc_file.parent.mkdir(parents=True, exist_ok=True)
    doc_file.write_text(document, encoding="utf-8")
    log.info(f"Documento generado: {doc_file}")

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
                try:
                    data = json.loads(session_file.read_text(encoding="utf-8"))
                    sessions.append({
                        "id": data["id"],
                        "companyName": data.get("companyName", "Sin nombre"),
                        "status": data.get("status", "unknown"),
                        "createdAt": data.get("createdAt", ""),
                        "messageCount": len(data.get("messages", [])),
                    })
                except Exception:
                    pass
    return {"sessions": sessions[:20]}

@app.get("/api/sessions/{session_id}/download")
async def download_document(session_id: str):
    session = get_session(session_id)
    if not session.get("document"):
        raise HTTPException(status_code=404, detail="Documento no generado aun")
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

@app.get("/api/agents")
async def list_agents_endpoint():
    return {"agents": load_agents()}

# --- Funciones auxiliares -----------------------------------------------------
def _detect_interview_complete(response: str, session: dict) -> bool:
    messages = session.get("messages", [])
    user_messages = [m for m in messages if m["role"] == "user"]
    if len(user_messages) < 6:
        return False
    closing_phrases = [
        "ya tengo suficiente informacion",
        "ya tengo suficiente informacion",
        "tengo toda la informacion",
        "hemos completado la entrevista",
        "con esta informacion puedo",
        "ya podemos generar",
        "listo para generar",
        "informacion recopilada",
        "resumen de lo que hemos",
        "a continuacion el resumen",
        "con estos datos podemos",
        "podemos proceder a generar",
        "estamos listos para crear",
    ]
    response_lower = response.lower()
    return any(phrase in response_lower for phrase in closing_phrases)

def _build_interview_summary(session: dict) -> str:
    messages = session.get("messages", [])
    lines = [f"# Informacion recopilada sobre: {session.get('companyName', 'la empresa')}\n"]
    for msg in messages:
        if msg["role"] == "user":
            lines.append(f"**Respuesta del cliente:** {msg['content']}")
        elif msg["role"] == "assistant":
            lines.append(f"**Pregunta del entrevistador:** {msg['content']}")
        lines.append("")
    return "\n".join(lines)

# --- Archivos estaticos -------------------------------------------------------
_ui_dir = PLUGIN_DIR / "app"
if _ui_dir.exists():
    log.info(f"Sirviendo UI desde: {_ui_dir}")
    app.mount("/ui", StaticFiles(directory=str(_ui_dir), html=True), name="ui")
else:
    log.warning(f"Directorio UI no encontrado: {_ui_dir}")

# --- Arranque -----------------------------------------------------------------
if __name__ == "__main__":
    log.info(f"Servidor iniciando en http://0.0.0.0:{PORT}")
    log.info(f"UI disponible en http://localhost:{PORT}/ui/index.html")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=True,
    )
