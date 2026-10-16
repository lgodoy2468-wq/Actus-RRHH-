# Actus Postulantes

Sistema privado de gestión de candidatos para **Actus & Asociados S.A.**

Aplicación web completa, independiente, con base de datos SQLite, autenticación real, roles, registro por texto/voz + interpretación inteligente, y diseño responsive igual a las capturas.

## Requisitos

- Python 3.10 o superior
- Navegador moderno (Chrome/Edge recomendado para voz)

## Instalación (en tu computadora)

```bash
# 1. Descargar o copiar la carpeta actus-postulantes

# 2. Crear entorno virtual (recomendado)
python3 -m venv venv
source venv/bin/activate          # Linux/Mac
# o: venv\Scripts\activate       # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar
python app.py
```

Abrí el navegador en: **http://127.0.0.1:5000**

## Usuarios iniciales

| Nombre          | Contraseña     | Rol         |
|-----------------|----------------|-------------|
| Administrador   | actus2026      | Admin       |
| María López     | reclutador123  | Reclutador  |

También podés entrar con el modo "Usuario individual" usando los emails:
- admin@actus.com.py / actus2026
- maria@actus.com.py / reclutador123

## Estructura de archivos

```
actus-postulantes/
├── app.py                 ← Toda la lógica (modelos, rutas, IA)
├── requirements.txt
├── instance/
│   └── actus.db           ← Base de datos (se crea sola)
├── static/
│   └── css/
│       └── style.css
└── templates/
    ├── base.html
    ├── login.html
    ├── panel.html
    ├── agregar_ia.html
    ├── postulantes.html
    ├── ver_postulante.html
    ├── ...
```

## Funciones principales

- Login con roles (Admin / Reclutador)
- Panel con contadores reales
- Registro manual de postulantes
- **Registro con IA** (texto o voz) que interpreta:
  - Nombre, cédula, vacante, corporativo
  - Persona de contacto (separada del corporativo)
  - Expectativa salarial en guaraníes
  - Mala referencia + motivo + empresa
- Prevención de cédulas duplicadas
- Búsqueda por cédula (con o sin puntos)
- Catálogos de Vacantes y Corporativos
- Registro confidencial de malas referencias
- Administración de usuarios (solo Admin)
- Auditoría de acciones

## Voz

Usa la Web Speech API del navegador (gratis).  
Funciona mejor en Chrome / Edge.  
En iOS Safari puede tener limitaciones.

## Producción

Para publicar en internet (gratis):

1. **Render.com** o **Railway.app** → subís el código, configurás el comando `python app.py`
2. Cambiá la `SECRET_KEY` en `app.py` por una cadena larga y aleatoria
3. La base SQLite se guarda en el disco del servicio (en planes gratuitos puede reiniciarse; para datos críticos usá PostgreSQL)

## Seguridad

- Contraseñas hasheadas (Werkzeug)
- Sesiones firmadas
- Roles verificados en el servidor
- No se exponen secretos al cliente
- Registro de actividad

---

Desarrollado según la especificación completa de Actus Postulantes.
