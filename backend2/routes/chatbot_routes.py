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
    Genera una pregunta tipo quiz basada en TODA la conversación enviada.
    Devuelve:
    - Pregunta
    - Lista de opciones
    - correct_answer_letter (A, B, C, D)
    - correct_answer_text (texto completo)
    """
    import json, re

    try:
        prompt = f"""
        You are an expert Meat Science tutor.

        Based ONLY on the following conversation context, generate ONE multiple-choice quiz question.
        The question must check the user's understanding and be about Meat Science.

        You MUST respond in **valid JSON only**, following this exact format:

        {{
          "question": "string",
          "options": ["option A", "option B", "option C", "option D"],
          "correct_answer_index": 0   // index from 0 to 3
        }}

        Context:
        {data.context}
        """

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return ONLY raw JSON. No explanations."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        raw = response.choices[0].message.content.strip()

        # ---------------------------
        # Intentar parseo JSON seguro
        # ---------------------------
        try:
            quiz_data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                quiz_data = json.loads(match.group(0))
            else:
                raise ValueError("No valid JSON found.")

        # ---------------------------
        # Validación mínima obligatoria
        # ---------------------------
        if "options" not in quiz_data or len(quiz_data["options"]) < 4:
            quiz_data["options"] = [
                "Protein", "Carbohydrates", "Lipids", "Vitamins"
            ]

        if "question" not in quiz_data or quiz_data["question"] == "":
            quiz_data["question"] = "Which nutrient is most abundant in meat?"

        if "correct_answer_index" not in quiz_data:
            quiz_data["correct_answer_index"] = 0

        correct_idx = int(quiz_data["correct_answer_index"])
        options = quiz_data["options"]

        # ---------------------------
        # DERIVAR LETRA Y TEXTO
        # ---------------------------
        correct_letter = chr(65 + correct_idx)  # A, B, C, D
        correct_text = options[correct_idx]

        # ---------------------------
        # 📤 Respuesta final
        # ---------------------------
        return {
            "question": quiz_data["question"],
            "options": options,
            "correct_answer_letter": correct_letter,
            "correct_answer_text": correct_text
        }

    except Exception as e:
        print(f"❌ generate_quiz failed: {e}")

        # FALLBACK SEGURO GARANTIZADO
        return {
            "question": "What is the main protein responsible for meat color?",
            "options": ["Myoglobin", "Collagen", "Elastin", "Actin"],
            "correct_answer_letter": "A",
            "correct_answer_text": "Myoglobin"
        }
