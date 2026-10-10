import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from settings import User, Quiz, QuizResult
from llm import generate_answer, evaluate_answer, check_answer
from database import (
    save_quiz,
    create_quiz_session,
    get_quiz_session,
    mark_quiz_session_submitted,
    get_all_history,
    get_history_by_id,
)

app = FastAPI(title="Quizwise API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    no_of_questions: int = Field(ge=1, le=30)
    level: Literal["easy", "medium", "hard"]


class SubmitRequest(BaseModel):
    session_id: str
    answers: list[list[str]]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/quiz/generate")
def generate_quiz(payload: GenerateRequest):
    try:
        user = User(
            content=payload.content.strip(),
            no_of_questions=payload.no_of_questions,
            level=payload.level,
        )
        quiz = generate_answer(user)
        if quiz is None or not quiz.questions:
            raise HTTPException(status_code=502, detail="The AI could not generate a quiz. Please try again.")
        if len(quiz.questions) != payload.no_of_questions:
            # Keep the generated result if the model returns a slightly different count.
            pass

        session_id = str(uuid.uuid4())
        create_quiz_session(session_id, datetime.now().isoformat(timespec="seconds"), quiz.model_dump())

        # Never send the answer key to the browser before the quiz is submitted.
        safe_quiz = {
            "topic": quiz.topic,
            "questions": [
                {
                    "question": q.question,
                    "type": q.type,
                    "options": q.options,
                    "difficulty": q.difficulty,
                }
                for q in quiz.questions
            ],
        }
        return {"session_id": session_id, "quiz": safe_quiz}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Quiz generation failed: {exc}") from exc


@app.post("/api/quiz/submit")
def submit_quiz(payload: SubmitRequest):
    stored = get_quiz_session(payload.session_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Quiz session not found. Please generate a new quiz.")
    if stored["submitted"]:
        raise HTTPException(status_code=409, detail="This quiz has already been submitted.")

    quiz = Quiz.model_validate(json.loads(stored["quiz"]))
    if len(payload.answers) != len(quiz.questions):
        raise HTTPException(status_code=400, detail="Please submit an answer for every question.")

    results = []
    for question, raw_answer in zip(quiz.questions, payload.answers):
        user_answer = [str(answer).strip() for answer in raw_answer if str(answer).strip()]

        if question.type in ("mcq", "multiple_answer"):
            is_correct = check_answer(question, user_answer)
            result = QuizResult(
                question=question.question,
                is_correct=is_correct,
                user_answer=user_answer,
                correct_answer=question.answer,
                description=question.description,
            )
        else:
            try:
                evaluation = evaluate_answer(question, user_answer)
                if evaluation is None:
                    raise RuntimeError("AI evaluation returned no result.")
                result = QuizResult(
                    question=question.question,
                    is_correct=evaluation.is_correct,
                    user_answer=evaluation.user_answer,
                    correct_answer=evaluation.correct_answer,
                    description=evaluation.description,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not evaluate a coding/theory answer. Please try submitting again. Details: {exc}",
                ) from exc

        results.append(result)

    score = sum(1 for result in results if result.is_correct)
    save_quiz(
        stored["date"],
        quiz.model_dump(),
        [result.model_dump() for result in results],
        score,
    )
    mark_quiz_session_submitted(payload.session_id)
    return {
        "score": score,
        "total": len(results),
        "results": [result.model_dump() for result in results],
    }


@app.get("/api/history")
def history():
    try:
        return {"items": get_all_history()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not load quiz history.") from exc


@app.get("/api/history/{quiz_id}")
def history_item(quiz_id: int):
    item = get_history_by_id(quiz_id)
    if not item:
        raise HTTPException(status_code=404, detail="Quiz history entry not found.")
    return item
