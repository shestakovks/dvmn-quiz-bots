import json
import string
from typing import Dict


def load_quiz_data(path_to_file: str) -> Dict:
    with open(path_to_file) as quiz_file:
        return json.load(quiz_file)


def strip_answer(answer: str) -> str:
    if "(" in answer:
        answer = answer.split("(")[0].strip()
    if "[" in answer and "]" in answer:
        # Fixing answers like '[Кукла] Барби.' or 'Перевели ["Улисса" Джеймса] Джойса.'
        lbracket_pos = answer.find("[")
        rbracket_pos = answer.find("]")
        answer = " ".join(
            [answer[:lbracket_pos].strip(), answer[rbracket_pos + 1 :].strip()]
        )
    answer = answer.strip(string.punctuation)
    return answer
