import os

def mostrar_estructura_carpeta(carpeta_raiz, exclude_dirs=None, indent_level=0):
    """
    Muestra la estructura de un proyecto, omitiendo carpetas como '__pycache__' y entornos virtuales.
    
    :param carpeta_raiz: Carpeta principal donde inicia el recorrido.
    :param exclude_dirs: Directorios a excluir (ej. '__pycache__', 'venv').
    :param indent_level: Nivel de indentación para mostrar la jerarquía de carpetas.
    """
    if exclude_dirs is None:
        exclude_dirs = ['__pycache__', 'venv', '.venv', '.git', '.idea']
    
    # Obtener la lista de archivos y carpetas en la carpeta actual
    try:
        items = os.listdir(carpeta_raiz)
    except PermissionError:
        print("⚠️ Permiso denegado para acceder a la carpeta:", carpeta_raiz)
        return

    # Filtrar los directorios a excluir
    items = [item for item in items if item not in exclude_dirs]

    for item in items:
        item_path = os.path.join(carpeta_raiz, item)

        # Si es una carpeta, la recorremos recursivamente
        if os.path.isdir(item_path):
            # Mostrar la carpeta actual con indentación
            print("  " * indent_level + f"├─ {item}/")
            mostrar_estructura_carpeta(item_path, exclude_dirs, indent_level + 1)

        # Si es un archivo, lo mostramos
        elif os.path.isfile(item_path):
            if item.lower().endswith(".pdf") or item.endswith("Dockerfile") or item.endswith("Makefileitem") or item.lower().endswith(".json") or item.lower().endswith(".py") or item.lower().endswith(".md") or item.lower().endswith(".txt") or item.lower().endswith(".env"):
                print("  " * indent_level + f"├─ {item}")

def generar_estructura(carpeta_raiz):
    """
    Función principal que genera la estructura del proyecto a partir de una carpeta raíz.
    """
    print(f"Proyecto en: {carpeta_raiz}")
    mostrar_estructura_carpeta(carpeta_raiz)

# Ruta de la carpeta raíz del proyecto (ajusta según la ubicación del proyecto)
carpeta_raiz = "C:/Users/HoneyMaldonado/Documents/googlerun"

# Ejecuta la generación de la estructura del proyecto
generar_estructura(carpeta_raiz)
