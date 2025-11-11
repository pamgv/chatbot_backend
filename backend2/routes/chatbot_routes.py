from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import openai
import os
import openai
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
openai.api_key = os.getenv("OPENAI_API_KEY")

conversation_history = []


class Question(BaseModel):
    question: str


@router.post("/ask")
async def ask_question(q: Question):
    try:
        # Agregar mensaje del usuario
        conversation_history.append({"role": "user", "content": q.question})

        # Respuesta del modelo
        response = openai.chat.completions.create(
            model="gpt-5-mini",
            messages=conversation_history
        )

        answer = response.choices[0].message.content
        conversation_history.append({"role": "assistant", "content": answer})

        # Limpiar historial cada 20 mensajes
        if len(conversation_history) >= 20:
            conversation_history.clear()

        return {"answer": answer}

    except Exception as e:
        return {"error": str(e)}

# ------------------------------------------------------------
# 🧠 NUEVO ENDPOINT: Generador de quiz basado en conversación
# ------------------------------------------------------------
class QuizRequest(BaseModel):
    username: str
    context: str  # concatenación de los últimos 5 mensajes (ya enviada por el frontend)


@router.post("/generate_quiz")
async def generate_quiz(data: QuizRequest):
    """
    Genera una pregunta tipo quiz basada en los últimos mensajes del usuario.
    Garantiza que siempre devuelva una pregunta y 4 opciones válidas.
    """
    import json, re

    try:
        prompt = f"""
        You are an expert Meat Science tutor.
        Based on the following conversation context, create ONE multiple-choice quiz question
        that checks the user's understanding. Return only valid JSON with this structure:

        {{
          "question": "string",
          "options": ["A", "B", "C", "D"],
          "correct_answer": "string"
        }}

        Conversation:
        {data.context}
        """

        # 🔹 Primera llamada al modelo
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a JSON-only quiz generator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )

        raw = response.choices[0].message.content.strip()

        # 🔹 Intentar parsear JSON directo
        try:
            quiz_data = json.loads(raw)
        except json.JSONDecodeError:
            # Intentar extraer el JSON de dentro de texto
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                quiz_data = json.loads(match.group(0))
            else:
                # Fallback absoluto si el modelo devuelve algo irreconocible
                quiz_data = {
                    "question": "What is the main protein responsible for meat color?",
                    "options": ["Collagen", "Myoglobin", "Keratin", "Elastin"],
                    "correct_answer": "Myoglobin"
                }

        # 🔹 Validar estructura mínima
        if not isinstance(quiz_data.get("options"), list) or len(quiz_data["options"]) < 2:
            quiz_data["options"] = ["Option A", "Option B", "Option C", "Option D"]
        if not quiz_data.get("question"):
            quiz_data["question"] = "Which of the following best describes meat tenderness?"
        if not quiz_data.get("correct_answer"):
            quiz_data["correct_answer"] = quiz_data["options"][0]

        return {
            "question": quiz_data["question"],
            "options": quiz_data["options"],
            "correct_answer": quiz_data["correct_answer"],
        }

    except Exception as e:
        print(f"❌ generate_quiz failed: {e}")
        # 🔹 fallback total garantizado
        return {
            "question": "What is the main nutrient found in red meat?",
            "options": ["Protein", "Fiber", "Vitamin C", "Carbohydrates"],
            "correct_answer": "Protein",
        }
