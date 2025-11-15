from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import openai
import os
from dotenv import load_dotenv
import json, re

load_dotenv()

router = APIRouter()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Memoria de conversación del endpoint /ask
conversation_history = []

# --------------------------
# 📌 Modelo de entrada
# --------------------------
class Question(BaseModel):
    question: str

class QuizRequest(BaseModel):
    username: str
    context: str


# --------------------------
# 🤖 Endpoint simple de chat
# --------------------------
@router.post("/ask")
async def ask_question(q: Question):
    try:
        conversation_history.append({"role": "user", "content": q.question})

        response = openai.chat.completions.create(
            model="gpt-5-mini",
            messages=conversation_history
        )

        answer = response.choices[0].message.content
        conversation_history.append({"role": "assistant", "content": answer})

        if len(conversation_history) >= 20:
            conversation_history.clear()

        return {"answer": answer}

    except Exception as e:
        return {"error": str(e)}


# --------------------------
# 🧠 Generador de QUIZ
# --------------------------
@router.post("/generate_quiz")
async def generate_quiz(data: QuizRequest):
    """
    Genera un quiz basado en TODO el contexto enviado.
    Devuelve pregunta, opciones, letra correcta (A-D) y texto correcto.
    """

    try:
        prompt = f"""
        You are an expert Meat Science tutor.

        Based ONLY on the following conversation context, generate ONE multiple-choice quiz question.

        Output ONLY valid JSON in this exact structure:

        {{
          "question": "string",
          "options": ["string1", "string2", "string3", "string4"],
          "correct_answer_index": 0
        }}

        Conversation:
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

        # --------------------------
        # Intentar parsear JSON válido
        # --------------------------
        try:
            quiz_data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                quiz_data = json.loads(match.group(0))
            else:
                raise ValueError("Invalid JSON returned by the model.")

        # --------------------------
        # Validaciones mínimas
        # --------------------------
        if "options" not in quiz_data or len(quiz_data["options"]) != 4:
            quiz_data["options"] = ["Protein", "Carbohydrates", "Lipids", "Vitamins"]

        if "question" not in quiz_data or not quiz_data["question"]:
            quiz_data["question"] = "Which nutrient is most abundant in meat?"

        if "correct_answer_index" not in quiz_data:
            quiz_data["correct_answer_index"] = 0

        correct_idx = int(quiz_data["correct_answer_index"])
        options = quiz_data["options"]

        correct_letter = chr(65 + correct_idx)   # A, B, C, D
        correct_text = options[correct_idx]

        # --------------------------
        # ✔ Respuesta final
        # --------------------------
        return {
            "question": quiz_data["question"],
            "options": options,
            "correct_answer_letter": correct_letter,
            "correct_answer_text": correct_text
        }

    except Exception as e:
        print("❌ generate_quiz failed:", e)
        return {
            "question": "What is the main nutrient found in meat?",
            "options": ["Protein", "Fiber", "Vitamin C", "Carbohydrates"],
            "correct_answer_letter": "A",
            "correct_answer_text": "Protein"
        }
