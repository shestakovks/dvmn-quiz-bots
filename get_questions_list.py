import argparse
import json
import os


def read_file(filename, encoding=None):
    with open(filename, encoding=encoding) as file:
        return file.read()


def save_quiz_list_json(quiz_list, path_to_file):
    with open(path_to_file, "w") as json_file:
        json.dump(quiz_list, json_file, ensure_ascii=False, indent=4)


def parse_block(block):
    result = {}
    key = ""
    block_lines = block.split("\n\n")
    for line in block_lines:
        if line.startswith("Вопрос"):
            key = line.split(":", 1)[1].strip()
        elif line.startswith("Ответ"):
            result[key] = line.split(":", 1)[1].strip()
    return result


def process_quiz_files(dir_path):
    dir_path = dir_path if dir_path.endswith("/") else dir_path + "/"
    quiz_files = [
        "".join([dir_path, filename])
        for filename in os.listdir(dir_path)
        if filename.endswith(".txt")
    ]
    quiz_dict = {}
    for quiz_file in quiz_files:
        quiz_blocks = read_file(quiz_file, encoding="KOI8-R").split("\n\n\n")
        for block in quiz_blocks:
            parsed_block = parse_block(block)
            quiz_dict.update(parsed_block)

    return quiz_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to directory with quiz files.")
    parser.add_argument("destination", help="Path to json file to save quiz data.")
    args = parser.parse_args()
    questions_list = process_quiz_files(args.path)
    save_quiz_list_json(questions_list, args.destination)
