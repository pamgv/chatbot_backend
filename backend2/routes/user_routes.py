from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.mongo_client import db
from datetime import datetime
from bson import ObjectId
import bcrypt
from openai import OpenAI  
import os
from dotenv import load_dotenv
from fastapi import Body

load_dotenv()

# Inicializar cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
router = APIRouter()

# Colecciones
users_col = db["users"]
messages_col = db["messages"]
games_col = db["games"]
quiz_col = db["quiz_results"]

# ---------------------------
# 🔹 Modelos de entrada
# ---------------------------
class Register(BaseModel):
    username: str
    password: str

class Login(BaseModel):
    username: str
    password: str

class Message(BaseModel):
    username: str
    text: str
    game_number: int
    question_number: int

class GameUpdate(BaseModel):
    username: str
    game_number: int
    question_number: int
    correct_count: int
    highest_score: int


# ---------------------------
# Funciones auxiliares
# ---------------------------
def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

def verify_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed)

def get_user(username: str):
    return users_col.find_one({"username": username})

def serialize_doc(doc):
    """Convierte ObjectId y datetime a tipos serializables por JSON"""
    if not doc:
        return None
    doc["_id"] = str(doc.get("_id"))
    if "user_id" in doc and isinstance(doc["user_id"], ObjectId):
        doc["user_id"] = str(doc["user_id"])
    if "timestamp" in doc and hasattr(doc["timestamp"], "isoformat"):
        doc["timestamp"] = doc["timestamp"].isoformat()
    if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
        doc["created_at"] = doc["created_at"].isoformat()
    return doc


# ---------------------------
# Registro de usuario
# ---------------------------
@router.post("/register")
def register_user(data: Register):
    if get_user(data.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_pw = hash_password(data.password)
    users_col.insert_one({
        "username": data.username,
        "password": hashed_pw,
        "best_score": 0,
        "current_game": 1,
        "stats": {"total_games": 0, "total_correct": 0},
        "created_at": datetime.utcnow()
    })
    return {"message": "User registered successfully!"}


# ---------------------------
# Inicio de sesión
# ---------------------------
@router.post("/login")
def login_user(data: Login):
    user = get_user(data.username)
    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return {"message": "Login successful!"}


# ---------------------------
# Guardar mensaje + respuesta del bot
# ---------------------------
@router.post("/save_message")
async def save_message(data: Message):
    user = get_user(data.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a helpful tutor chatbot for Meat Science."},
                {"role": "user", "content": data.text}
            ]
        )

        bot_reply = response.choices[0].message.content

        messages_col.insert_one({
            "user_id": ObjectId(user["_id"]),
            "username": data.username,
            "user_message": data.text,
            "bot_response": bot_reply,
            "game_number": data.game_number,
            "question_number": data.question_number,
            "created_at": datetime.utcnow()
        })

        return {
            "username": data.username,
            "user_message": data.text,
            "bot_response": bot_reply,
            "status": "Message and response saved successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI or DB error: {str(e)}")

# ---------------------------
# Actualizar progreso del juego (versión final con total_games correcto)
# ---------------------------
@router.post("/update_game")
def update_game(data: GameUpdate):
    user = get_user(data.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = ObjectId(user["_id"])

    # Verificar si el juego ya existe
    existing_game = games_col.find_one({
        "user_id": user_id,
        "game_number": data.game_number
    })

    # Si el juego no existe → crear uno nuevo y aumentar total_games
    if not existing_game:
        games_col.insert_one({
            "user_id": user_id,
            "game_number": data.game_number,
            "question_number": data.question_number,
            "correct_count": data.correct_count,
            "created_at": datetime.utcnow()
        })

        # Solo sumar total_games cuando es un NUEVO juego
        users_col.update_one(
            {"_id": user["_id"]},
            {"$inc": {"stats.total_games": 1}}
        )

        print(f"Nuevo juego creado para {data.username}, total_games incrementado.")
    else:
        # Actualizar progreso del juego existente
        games_col.update_one(
            {"user_id": user_id, "game_number": data.game_number},
            {"$set": {
                "question_number": data.question_number,
                "correct_count": data.correct_count
            }}
        )
        print(f"Juego existente actualizado para {data.username}.")

    # Actualizar récord personal si aplica
    if data.highest_score > user.get("best_score", 0):
        users_col.update_one(
            {"_id": user["_id"]},
            {"$set": {"best_score": data.highest_score}}
        )

    return {"message": "Game progress updated successfully!"}

# ---------------------------
# Guardar resultado de quiz
# ---------------------------
@router.post("/save_quiz_result")
def save_quiz_result(
    username: str = Body(...),
    game_number: int = Body(...),
    question_number: int = Body(...),
    quiz_question: str = Body(...),
    quiz_options: list = Body(...),
    selected_option: str = Body(...),
    correct_answer_letter: str = Body(...),
    correct_answer_text: str = Body(...),
    is_correct: bool = Body(...),
):
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = ObjectId(user["_id"])

    quiz_col.insert_one({
        "user_id": user_id,
        "username": username,
        "game_number": game_number,
        "question_number": question_number,
        "quiz_question": quiz_question,
        "quiz_options": quiz_options,
        "selected_option": selected_option,
        "correct_answer_letter": correct_answer_letter,
        "correct_answer_text": correct_answer_text,
        "is_correct": is_correct,
        "created_at": datetime.utcnow()
    })

    games_col.update_one(
        {"user_id": user_id, "game_number": game_number},
        {
            "$set": {"question_number": question_number},
            "$inc": {"correct_count": 1 if is_correct else 0}
        },
        upsert=True
    )

    users_col.update_one(
        {"_id": user_id},
        {"$inc": {"stats.total_correct": 1 if is_correct else 0}}
    )

    return {
        "message": "Quiz result saved",
        "is_correct": is_correct,
        "correct_answer_letter": correct_answer_letter,
        "correct_answer_text": correct_answer_text
    }


# Función auxiliar para serializar cualquier ObjectId → str
def serialize_doc(doc):
    """Convierte todos los ObjectId en strings para que FastAPI los pueda devolver."""
    if not doc:
        return doc
    return {k: str(v) if isinstance(v, ObjectId) else v for k, v in doc.items()}

@router.get("/get_stats/{username}")
def get_stats(username: str):
    try:
        user = get_user(username)
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")

        # Aseguramos ObjectId correcto
        user_id = user["_id"] if isinstance(user["_id"], ObjectId) else ObjectId(user["_id"])

        # Traemos juegos y mensajes por ObjectId
        games = list(games_col.find({"user_id": user_id}))
        messages = list(messages_col.find({"user_id": user_id}))

        # Serializamos para evitar error con ObjectId
        games = [serialize_doc(g) for g in games]
        messages = [serialize_doc(m) for m in messages]

        # Sincronizar total_games según cantidad real
        real_total_games = len(games)
        user_stats = user.get("stats") or {"total_games": 0, "total_correct": 0}

        if real_total_games != user_stats.get("total_games", 0):
            users_col.update_one(
                {"_id": user_id},
                {"$set": {"stats.total_games": real_total_games}}
            )
            user_stats["total_games"] = real_total_games

        # Devolver estructura limpia y serializable
        return {
            "username": username,
            "best_score": user.get("best_score", 0),
            "total_games": user_stats.get("total_games", 0),
            "total_correct": user_stats.get("total_correct", 0),
            "games": games,
            "messages": messages
        }

    except Exception as e:
        print("Error in get_stats:", str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.get("/debug_user_links/{username}") 
def debug_user_links(username: str): 
    user = get_user(username) 
    if not user: raise HTTPException(status_code=404, detail=f"User '{username}' not found") 
    
    user_id = user["_id"] 
    uid_str = str(user_id) 
    uid_obj = ObjectId(uid_str) 
    # 
    # Cuántos documentos coinciden por cada tipo 
    # 
    count_obj_games = games_col.count_documents({"user_id": uid_obj}) 
    count_str_games = games_col.count_documents({"user_id": uid_str}) 
    count_obj_msgs = messages_col.count_documents({"user_id": uid_obj}) 
    count_str_msgs = messages_col.count_documents({"user_id": uid_str}) 
    sample_games = list(games_col.find({"user_id": uid_str}, {"_id": 0}))
    sample_msgs = list(messages_col.find({"user_id": uid_str}, {"_id": 0}))

    return { "user_id_type": str(type(user_id)), 
            "user_id_str": uid_str, 
            "match_counts": 
            { 
                "games_by_objectid": count_obj_games,
                "games_by_string": count_str_games, 
                "messages_by_objectid": count_obj_msgs, 
                "messages_by_string": count_str_msgs 
            }, 
              "sample_games_user_ids": sample_games, 
              "sample_messages_user_ids": sample_msgs }

@router.get("/get_game_messages/{username}/{game_number}")
def get_game_messages(username: str, game_number: int):
    """
    Devuelve todos los mensajes de un usuario en un juego específico,
    correctamente filtrando por ObjectId y serializando la salida.
    """
    try:
        # Buscar usuario
        user = get_user(username)
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")

        # Asegurar que user_id sea ObjectId
        user_id = user["_id"] if isinstance(user["_id"], ObjectId) else ObjectId(user["_id"])

        # Buscar mensajes correspondientes al juego
        msgs = list(messages_col.find(
            {"user_id": user_id, "game_number": int(game_number)},
            {"_id": 0}
        ))

        # Ordenar por número de pregunta
        msgs.sort(key=lambda x: x.get("question_number", 0))

        # Serializar mensajes
        serialized_msgs = [serialize_doc(m) for m in msgs]

        return {
            "username": username,
            "game_number": int(game_number),
            "messages": serialized_msgs
        }

    except Exception as e:
        print(f"Error in get_game_messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.delete("/delete_all_messages/{username}")
def delete_all_messages(username: str):
    """Elimina todas las conversaciones (mensajes) y juegos de un usuario."""
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = str(user["_id"])

    messages_col.delete_many({"user_id": user_id})
    games_col.delete_many({"user_id": user["_id"]})

    users_col.update_one({"_id": user["_id"]}, {"$set": {"stats.total_games": 0, "stats.total_correct": 0}})

    return {"message": f"All conversations deleted for {username}"}

@router.get("/quiz_history/{username}")
def quiz_history(username: str):
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = ObjectId(user["_id"])

    quizzes = list(quiz_col.find({"user_id": user_id}).sort("created_at", 1))

    # Convert ObjectId → string
    quizzes = [serialize_doc(q) for q in quizzes]

    return {
        "username": username,
        "total_quizzes": len(quizzes),
        "quizzes": quizzes
    }








