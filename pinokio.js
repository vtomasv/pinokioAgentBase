module.exports = {
  title: "Estructura de Marca Corporativa",
  description: "Crea documentos de estructura de marca corporativa mediante entrevista guiada con IA",
  icon: "icon.png",
  version: "1.1.0",

  menu: async (kernel, info) => {
    // Detectar si ya esta instalado (carpeta env del venv)
    const installed = await kernel.exists(__dirname, "venv")
    // Detectar si el servidor esta corriendo
    const running = await kernel.script.running(__dirname, "start.json")

    if (!installed) {
      return [{
        default: true,
        icon: "fa-solid fa-download",
        text: "Instalar",
        href: "install.json",
        description: "Instalacion automatica con 1 click"
      }]
    }

    if (running) {
      return [
        {
          icon: "fa-solid fa-circle",
          text: "En ejecucion",
          href: "start.json",
          style: "color: #22c55e"
        },
        {
          icon: "fa-solid fa-arrow-up-right-from-square",
          text: "Abrir",
          href: "http://localhost:{{port}}/ui/index.html",
          description: "Abrir la interfaz del plugin"
        },
        {
          icon: "fa-solid fa-stop",
          text: "Detener",
          href: "stop.json"
        }
      ]
    }

    return [
      {
        default: true,
        icon: "fa-solid fa-play",
        text: "Iniciar",
        href: "start.json",
        description: "Iniciar el plugin"
      },
      {
        icon: "fa-solid fa-rotate",
        text: "Reinstalar",
        href: "install.json",
        description: "Reinstalar si hay problemas"
      }
    ]
  }
}
