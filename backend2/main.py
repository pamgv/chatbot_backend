#------- Nuevo código ----------#
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.chatbot_routes import router as chatbot_router
from routes.user_routes import router as user_router
import openai
import os
from dotenv import load_dotenv

app = FastAPI(title="Chatbot Game Backend")

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# 👇 Agrega esta sección CORS justo después de crear la app
origins = [
    "https://chatbotfrontend2-pb7qpgatu-pamgvs-projects.vercel.app",  # dominio actual de Vercel
    "https://chatbotfrontend2-ito1a3v3o-pamgvs-projects.vercel.app",  # dominio de tu frontend en Vercel
    "https://chatbotfrontend2-b1k0noud9-pamgvs-projects.vercel.app",
    "http://localhost:5173",                                          # para desarrollo local
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chatbot_router, prefix="/chatbot", tags=["Chatbot"])
app.include_router(user_router, prefix="/user", tags=["Users"])

@app.get("/")
def root():
    return {"message": "🚀 Chatbot backend modular running and connected to MongoDB!"}





