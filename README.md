# Estructura de Marca Corporativa - Plugin Pinokio

Plugin de IA local que orquesta dos agentes LLM especializados para crear documentos profesionales de estructura de marca corporativa mediante una entrevista guiada.

## 🎯 Características

- **Entrevista Estructurada**: Agente especializado que realiza preguntas estratégicas sobre tu marca
- **Generación Automática**: Segundo agente que crea un documento profesional basado en las respuestas
- **100% Local**: Todos los datos se procesan localmente con Ollama - sin enviar información a servidores externos
- **Instalación 1-Click**: Instalación completamente automática sin configuración manual
- **Persistencia en Disco**: Todas las sesiones y documentos se guardan localmente
- **Interfaz Moderna**: UI intuitiva diseñada para usuarios sin experiencia técnica

## 🚀 Instalación Rápida

1. Abre [Pinokio](https://pinokio.co)
2. Ve a "Discover" y pega esta URL:
   ```
   https://github.com/tu-usuario/pinokioAgentBase/tree/main/brand-structure-plugin
   ```
3. Haz click en **"Instalar"** (solo 1 click)
4. Espera la instalación automática (5-15 minutos la primera vez)
5. Haz click en **"Iniciar"**

## 📋 Requisitos

- Pinokio instalado
- 8GB RAM mínimo (16GB recomendado para mejor rendimiento)
- 5GB espacio libre en disco
- Conexión a internet (solo para la instalación inicial)

## 🤖 Cómo Funciona

### Fase 1: Entrevista
El **Agente Entrevistador** (llama3.1:8b) realiza una serie de preguntas estratégicas sobre tu empresa:
- Visión y misión
- Valores corporativos
- Público objetivo
- Diferenciadores competitivos
- Personalidad de marca
- Propuesta de valor
- Tono de comunicación
- Objetivos de negocio

### Fase 2: Generación de Documento
El **Agente Generador** (llama3.1:8b) crea un documento profesional que incluye:
- Resumen ejecutivo
- Identidad corporativa (visión, misión, valores)
- Identidad de marca (personalidad, tono, voz)
- Análisis de público objetivo
- Propuesta de valor única
- Posicionamiento competitivo
- Directrices de comunicación
- Recomendaciones estratégicas
- Roadmap de implementación

## 💾 Almacenamiento de Datos

Todos los datos se guardan en `~/pinokio/api/brand-structure-plugin/data/`:
- `sessions/` - Historial de entrevistas
- `exports/` - Documentos generados (formato Markdown)
- `agents/` - Configuración de agentes
- `prompts/` - System prompts personalizables

## 🛠️ Personalización

### Editar Prompts
Los system prompts se encuentran en:
- `defaults/prompts/interviewer.md` - Prompt del entrevistador
- `defaults/prompts/document_generator.md` - Prompt del generador

Puedes editarlos directamente en el archivo para cambiar el comportamiento de los agentes.

### Cambiar Modelos
En `defaults/agents.json`, modifica el campo `"model"` para usar diferentes modelos:
- `llama3.2:1b` - Muy rápido (2GB RAM)
- `llama3.2:3b` - Rápido (4GB RAM)
- `llama3.1:8b` - Balanceado (8GB RAM) ← Recomendado
- `mistral:7b` - Especializado en código (8GB RAM)

## 📊 Modelos Disponibles

| Modelo | RAM Mín. | Velocidad | Mejor para |
|--------|----------|-----------|-----------|
| llama3.2:1b | 2GB | Muy rápido | Pruebas rápidas |
| llama3.2:3b | 4GB | Rápido | Uso general |
| llama3.1:8b | 8GB | Medio | Calidad profesional ← Predeterminado |
| mistral:7b | 8GB | Rápido | Análisis técnico |

## 🔒 Privacidad y Seguridad

- ✅ 100% offline - sin conexión a internet después de la instalación
- ✅ Datos locales - nunca se envían a servidores externos
- ✅ Modelos locales - Ollama ejecuta todo en tu PC
- ✅ Código abierto - puedes revisar toda la lógica

## 🐛 Solución de Problemas

### "Ollama no disponible"
```bash
# Instalar Ollama manualmente
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

### "Modelo no encontrado"
El plugin descargará automáticamente el modelo durante la instalación. Si falla:
```bash
ollama pull llama3.1:8b
```

### "Memoria insuficiente"
Usa un modelo más pequeño editando `defaults/agents.json` y cambia:
```json
"model": "llama3.2:3b"
```

## 📝 Estructura del Documento Generado

El documento incluye:
1. **Portada** - Nombre de la empresa
2. **Resumen Ejecutivo** - Síntesis de la marca
3. **Identidad Corporativa** - Visión, misión, valores
4. **Identidad de Marca** - Personalidad, tono, voz
5. **Público Objetivo** - Segmentación y buyer personas
6. **Propuesta de Valor** - PVU y beneficios
7. **Posicionamiento** - Diferenciadores y ventajas
8. **Comunicación** - Directrices y ejemplos
9. **Estrategia** - Recomendaciones accionables
10. **Roadmap** - Plan de implementación a 90 días

## 🎨 Casos de Uso

- **Startups**: Definir identidad de marca desde cero
- **Pymes**: Mejorar y documentar estrategia de marca
- **Rediseño**: Actualizar estructura de marca existente
- **Consultoría**: Base para propuestas de branding
- **Marketing**: Alineación interna de marca

## 📞 Soporte

Para reportar bugs o sugerencias:
1. Abre un issue en el repositorio
2. Describe el problema con detalles
3. Incluye capturas de pantalla si es necesario

## 📄 Licencia

MIT - Libre para usar, modificar y distribuir

## 🙏 Créditos

Desarrollado con Pinokio y Ollama para traer IA profesional a pymes sin costo.

---

**Nota**: Este plugin requiere Ollama instalado. Los modelos LLM se descargan automáticamente durante la instalación.
