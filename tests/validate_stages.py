import json
import sys

with open("curriculum/stages.json", encoding="utf-8") as f:
    data = json.load(f)

stages = data["stages"]
total_themes = 0
total_questions = 0
errors = []

for stage in stages:
    themes = stage["themes"]
    total_themes += len(themes)
    print(f"STAGE {stage['id']}: {stage['title']} -- {len(themes)} themes")
    for theme in themes:
        quiz = theme["quiz"]
        total_questions += len(quiz)
        if len(quiz) != 3:
            errors.append(f"  BAD quiz count: {theme['id']} = {len(quiz)}")
        for q in quiz:
            if len(q["choices"]) != 4:
                errors.append(f"  BAD choices: {q['id']} = {len(q['choices'])}")
            if q["correct_index"] not in range(4):
                errors.append(f"  BAD correct_index: {q['id']}")
        print(f"  {theme['id']}: {theme['title']} ({len(quiz)} questions)")

print()
print(f"stages:    {len(stages)} (expected 5)")
print(f"themes:    {total_themes} (expected 25)")
print(f"questions: {total_questions} (expected 75)")

if errors:
    print("\nERRORS:")
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("\nALL OK - structure is valid")
