module.exports = {
  title: "Estructura de Marca Corporativa",
  description: "Crea documentos de estructura de marca corporativa mediante entrevista guiada con IA",
  icon: "icon.png",
  version: "1.0.0",
  
  menu: async (kernel, info) => {
    const installed = await kernel.exists(__dirname, "venv")
    const running = await kernel.script.running(__dirname, "start.js")
    
    if (!installed) {
      return [{
        default: true,
        icon: "fa-solid fa-download",
        text: "Instalar",
        href: "install.js",
        description: "Instalación automática con 1 click"
      }]
    }
    
    if (running) {
      return [
        {
          icon: "fa-solid fa-circle",
          text: "En ejecución",
          href: "start.js",
          style: "color: #22c55e"
        },
        {
          icon: "fa-solid fa-arrow-up-right-from-square",
          text: "Abrir",
          href: "start.js",
          description: "Abrir el plugin"
        },
        {
          icon: "fa-solid fa-stop",
          text: "Detener",
          href: "stop.js"
        }
      ]
    }
    
    return [
      {
        default: true,
        icon: "fa-solid fa-play",
        text: "Iniciar",
        href: "start.js",
        description: "Iniciar el plugin"
      },
      {
        icon: "fa-solid fa-rotate",
        text: "Reinstalar",
        href: "install.js",
        description: "Reinstalar si hay problemas"
      }
    ]
  }
}
