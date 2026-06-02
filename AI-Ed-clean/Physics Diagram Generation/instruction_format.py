import json
from pathlib import Path
from typing import List, Literal, Sequence, Union

Schema = Literal["plain", "chat"]


def make_problem_code_json(
    problems: Sequence[str],
    py_files: Sequence[Union[str, Path]],
    out_jsonl: Union[str, Path],
    schema: Schema = "plain",
    system_prompt: str = "You are a helpful coding assistant that will draw a diagram for given problems."
) -> None:
    """
    Build a JSONL dataset from (problems, python files).

    Pairing rule: pairs by index (order). If counts differ, uses the min length.

    Args:
        problems: list of problem statements (strings).
        py_files: list of paths to .py files (same order as problems).
        out_jsonl: output path for the JSONL file.
        schema: "plain" -> {"problem":..., "code":...}
                "chat"  -> {"messages":[
                               {"role":"system","content":...},
                               {"role":"user","content":<problem>},
                               {"role":"assistant","content":<code>}
                             ]}
        system_prompt: used only for schema="chat".
    """
    out_path = Path(out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalize file paths and read code
    codes: List[str] = []
    for p in py_files:
        p = Path(p)
        if not p.exists():
            raise FileNotFoundError(f"Missing file: {p}")
        # Read text as UTF-8, fallback to latin-1 if needed
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = p.read_text(encoding="latin-1")
        codes.append(text)

    n = min(len(problems), len(codes))
    if n == 0:
        raise ValueError("No pairs to write: empty problems or files.")
    if len(problems) != len(codes):
        print(f"[warn] Length mismatch: problems={len(problems)} files={len(codes)}. "
              f"Writing the first {n} pairs.")

    with out_path.open("w", encoding="utf-8") as f:
        for i in range(n):
            problem = problems[i].strip()
            code = codes[i].rstrip()  # keep code formatting; trim trailing newlines

            if schema == "plain":
                rec = {"problem": problem, "code": code}
            elif schema == "chat":
                rec = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": problem},
                        {"role": "assistant", "content": code},
                    ]
                }
            else:
                raise ValueError(f"Unknown schema: {schema}")

            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# --------------------------
# Example usage
# --------------------------
if __name__ == "__main__":
    train_problems = [
        "A block of mass m rests on a 30° incline. Draw a free body diagram with W, N, and friction f, and draw decomposition of weight into parallel and perpendicular directions to the incline."
    ]
    train_files = ["data/FreeBodyCode.py"]

    # Plain (problem, code) pairs
    make_problem_code_json(train_problems, train_files, "data/train.jsonl", schema="plain")

    # Chat-style pairs (useful for instruction tuning on Qwen/LLMs)
    make_problem_code_json(
        train_problems,
        train_files,
        "data/train_chat.jsonl",
        schema="chat",
        system_prompt="You are a helpful coding assistant that will draw a diagram for given problems."
    )


    eval_problems = [
        "A block of mass m rests on a 30° incline. Draw a free body diagram with W, N, and friction f, and draw decomposition of weight into parallel and perpendicular directions to the incline."
    ]

    eval_files = ["data/FreeBodyCode.py"]


    make_problem_code_json(eval_problems, train_files, "data/eval.jsonl", schema="plain")

    make_problem_code_json(
        eval_problems,
        eval_files,
        "data/eval_chat.jsonl",
        schema="chat",
        system_prompt="You are a helpful coding assistant that will draw a diagram for given problems."
    )


