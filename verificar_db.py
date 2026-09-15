import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

MSYS2_BIN = r'C:\msys64\ucrt64\bin'
if os.path.isdir(MSYS2_BIN):
    os.add_dll_directory(MSYS2_BIN)
    os.environ['PATH'] = MSYS2_BIN + os.pathsep + os.environ.get('PATH', '')
os.environ['WEASYPRINT_DLL_DIRECTORIES'] = MSYS2_BIN

from dotenv import load_dotenv
load_dotenv('.env')

from app import create_app
app = create_app()

print("=== VERIFICACION DEL CHATBOT ===")
print(f"App creada correctamente")

ai = app.config.get('AI_SERVICE')
if ai:
    print(f"GeminiAIService: INICIALIZADO")
    print(f"Disponible: {ai.esta_disponible()}")
else:
    print("GeminiAIService: NO inicializado (verificar GEMINI_API_KEY)")

# Verificar la ruta /api/chat existe
rules = [str(r) for r in app.url_map.iter_rules() if 'chat' in str(r)]
print(f"Rutas del chatbot: {rules}")

print()
print("RESULTADO: Sistema listo para el chatbot.")
