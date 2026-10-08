"""One-off migration of the worked example's recorded lesson and note to the v2 contracts.

Run from the repository root:  python3 examples/linear_independence/tools/migrate_v2.py
"""

import json
from pathlib import Path

REC = Path(__file__).resolve().parent.parent / "recorded"


def load(name):
    return json.loads((REC / f"{name}.json").read_text(encoding="utf-8"))


def save(name, data):
    (REC / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def step(matrix, ops=None, highlight=(), label="", aug=None):
    return {"matrix": matrix, "augmented_col": aug, "row_ops": ops or [], "highlight": list(highlight), "label": label}


def hl(row, col, role):
    return {"row": row, "col": col, "role": role}


def figure(kind, title, caption="", steps=(), lines=(), nodes=(), edges=()):
    return {"kind": kind, "title": title, "caption": caption, "steps": list(steps), "lines": list(lines),
            "nodes": list(nodes), "edges": list(edges)}


DEP_FIG = figure(
    "row_reduction", "(1,2), (2,4)를 열로 세워 행 줄이기",
    "두 번째 열에 선도 1이 없다. 그 열의 계수 $c_2$는 자유롭게 고를 수 있으므로 자명하지 않은 해가 있다.",
    steps=[
        step([["1", "2"], ["2", "4"]], label="계수행렬"),
        step([["1", "2"], ["0", "0"]], ["", "R_2 - 2R_1"], [hl(0, 0, "pivot"), hl(1, 0, "eliminate"), hl(0, 1, "free"), hl(1, 1, "free")], "행사다리꼴"),
    ],
)
SPAN_FIG = figure(
    "lines_2d", "span{(1,0)}과 span{(0,1)}",
    "(1,0) 하나로는 x축($y = 0$) 위만, (0,1) 하나로는 y축($x = 0$) 위만 갈 수 있다. 둘을 함께 쓰면 평면 전체로 갈 수 있다.",
    lines=[{"a": 0, "b": 1, "c": 0, "label": "span{(1,0)}: y = 0"}, {"a": 1, "b": 0, "c": 0, "label": "span{(0,1)}: x = 0"}],
)
TEST_FLOW = figure(
    "flow", "일차독립 판정 순서", "",
    nodes=[
        {"id": "a", "label": "벡터들을 열로 세운 행렬 $A$"},
        {"id": "b", "label": "$A\\mathbf{c} = \\mathbf{0}$을 행 줄이기"},
        {"id": "c", "label": "자유변수가 있는가?"},
        {"id": "d", "label": "일차종속"},
        {"id": "e", "label": "일차독립"},
    ],
    edges=[{"from": "a", "to": "b", "label": ""}, {"from": "b", "to": "c", "label": ""},
           {"from": "c", "to": "d", "label": "있다"}, {"from": "c", "to": "e", "label": "없다"}],
)

PROOFS = {
    "C2": [{"theorem_ref": "T1", "statement": "span{v1, ..., vk}는 V의 부분공간이다.", "method": "direct",
            "proof_markdown": "1. 모든 계수를 0으로 두면 영벡터가 나온다. 그래서 영벡터가 span 안에 있다.\n2. 두 일차결합을 더하면 계수끼리 더한 일차결합이다. 그래서 덧셈에 닫혀 있다.\n3. 일차결합에 스칼라 $k$를 곱하면 계수가 모두 $k$배된 일차결합이다. 그래서 스칼라배에 닫혀 있다.\n\n세 조건을 만족하므로 부분공간이다."}],
    "C3": [{"theorem_ref": "T2", "statement": "v1, ..., vk가 일차종속 ⇔ 어떤 vj가 나머지 벡터들의 일차결합으로 표현된다.", "method": "direct",
            "proof_markdown": "(⇒) 모두 0은 아닌 계수로 $c_1v_1 + \\cdots + c_kv_k = 0$이라 하자. $c_j \\neq 0$인 $j$를 고르고 양변을 $c_j$로 나누면 $v_j$가 나머지의 일차결합으로 정리된다.\n\n(⇐) $v_j = a_1v_1 + \\cdots + a_kv_k$($v_j$ 항 제외)라 하자. 이항하면 $v_j$의 계수가 $-1$인 일차결합이 0이 된다. 계수 $-1 \\neq 0$이므로 일차종속이다."},
           {"theorem_ref": None, "statement": "'어느 두 벡터도 평행하지 않으면 일차독립'은 거짓이다.", "method": "counterexample",
            "proof_markdown": "$\\mathbb{R}^3$의 $(1,0,0)$, $(0,1,0)$, $(1,1,0)$은 어느 둘도 평행하지 않다. 하지만 $(1,0,0) + (0,1,0) - (1,1,0) = 0$이다. 계수가 모두 0은 아니므로 일차종속이다."}],
}
EXAM = {
    "C2": [{"type": "concept", "difficulty": "basic", "prompt_markdown": "$\\operatorname{span}\\{(1,0),(0,1)\\} = \\mathbb{R}^2$인 이유를 설명하라.",
            "answer_markdown": "모든 $(a,b)$를 $a(1,0) + b(0,1)$로 쓸 수 있기 때문이다.",
            "solution_markdown": "임의의 $(a,b) \\in \\mathbb{R}^2$에 대해 $(a,b) = a(1,0) + b(0,1)$. 그래서 $\\mathbb{R}^2$의 모든 벡터가 span 안에 있다.",
            "why_likely": "교안 예제(E1)와 판서 설명(P2)이 직접 다룬다.", "basis_refs": ["E1", "P2"]}],
    "C3": [{"type": "computation", "difficulty": "standard", "prompt_markdown": "$(1,2)$, $(2,4)$가 일차종속임을 보여라.",
            "answer_markdown": "$2(1,2) - (2,4) = 0$.",
            "solution_markdown": "$(2,4) = 2(1,2)$이므로 계수 $(2, -1)$로 영벡터를 만들 수 있다. 계수가 모두 0은 아니므로 일차종속이다.",
            "why_likely": "교안 예제(E2)와 '★ 중요: 자명한 해만 존재하는가?'(P1)", "basis_refs": ["E2", "P1"]},
           {"type": "true_false", "difficulty": "basic", "prompt_markdown": "영벡터를 포함한 벡터 묶음은 일차독립일 수 있다. (참/거짓)",
            "answer_markdown": "거짓", "solution_markdown": "영벡터의 계수만 1, 나머지를 0으로 두면 0이 아닌 계수로 영벡터가 만들어진다.",
            "why_likely": "판서의 주의 표시(P4)", "basis_refs": ["P4"]}],
}
DETAIL = {
    "P2": ("span은 '만들 수 있는 것 전부'라는 집합이다. 벡터 하나가 아니라 무수히 많은 벡터의 모음이라는 점을 기억해야 한다.",
           "span을 처음 보면 어렵게 느껴지는데요, 재료로 쓸 벡터 몇 개를 정해 두고 그걸로 섞어서 만들 수 있는 걸 전부 모았다고 생각하면 돼요."),
    "P1": ("일차독립 판정은 결국 '영벡터를 만드는 계수가 전부 0인 것뿐인가'를 묻는 것이다. 이 질문 하나로 정의와 판정이 모두 정리된다.",
           "모든 계수를 0으로 두면 영벡터가 나오는 건 당연하죠. 문제는 그것 말고 다른 방법이 있느냐예요. 그게 없으면 독립이에요."),
    "P3": ("일차독립을 span과 연결한 설명이다. 독립인 묶음에서는 어떤 벡터도 다른 벡터들로 대신할 수 없으므로, 빼면 만들 수 있는 범위가 줄어든다.",
           "쓸데없는 벡터가 없다는 게 무슨 뜻이냐면, 하나라도 빼면 만들 수 있는 게 줄어든다는 거예요."),
    "P4": ("영벡터가 있으면 그 계수만 1로 두어도 영벡터가 만들어진다. 그래서 판정할 필요도 없이 종속이다.",
           "영벡터가 하나라도 끼어 있으면 바로 종속이에요. 그 벡터 앞에 1을 붙이고 나머지는 0으로 두면 끝이니까요."),
    "P5": ("일차독립 판정을 동차연립방정식 문제로 바꾸는 방법이다. 벡터를 열로 세운 행렬의 동차방정식이 자명해만 가지는지 확인한다.",
           None),
    "P6": ("기저는 span과 일차독립을 동시에 만족하는 벡터 묶음으로 다음 강의에서 다룬다(내 필기 기록).", None),
}


def migrate_lesson():
    lesson = load("intuition_teacher")
    if lesson["schema"] == "math_intuition_lesson/2":
        return
    lesson["schema"] = "math_intuition_lesson/2"
    for item in lesson["lessons"]:
        cid = item["concept_id"]
        for p in item["professor_points"]:
            detail, recon = DETAIL[p["emphasis_ref"]]
            p["detail"] = detail
            p["reconstruction"] = recon
        item["proofs"] = PROOFS.get(cid, [])
        item["figures"] = {"C2": [SPAN_FIG], "C3": [DEP_FIG, TEST_FLOW]}.get(cid, [])
        item["exam_items"] = EXAM.get(cid, [])
    save("intuition_teacher", lesson)


def block(kind, title, body, refs, status, figure=None, reconstruction=None, proof_method=None):
    return {"kind": kind, "title": title, "body_markdown": body, "refs": refs, "status": status,
            "figure": figure, "reconstruction": reconstruction, "proof_method": proof_method}


KIND_OF = {"core": "definition", "formulas": "explanation", "example": "example", "pitfalls": "warning",
           "intuition": "intuition", "why": "why", "one_line": "intuition", "previous_link": "connection",
           "relations": "connection"}
MAIN_ORDER = ["core", "formulas", "example", "professor", "pitfalls"]
SUPPORT_ORDER = ["one_line", "why", "intuition", "relations", "previous_link"]


def migrate_note():
    note = load("note_editor")
    if note["schema"] == "math_study_note/2":
        return
    entries = []
    for entry in note["entries"]:
        cid = entry["concept_id"]
        secs = {s["key"]: s for s in entry["sections"]}
        blocks = []
        for key in MAIN_ORDER:
            s = secs.get(key)
            if not s:
                continue
            if key == "professor":
                ref = s["refs"][0]
                recon = " ".join(DETAIL[r][1] for r in s["refs"] if DETAIL[r][1]) or None
                detail = " ".join(DETAIL[r][0] for r in s["refs"])
                blocks.append(block("professor", "", s["body_markdown"] + "\n\n" + detail, s["refs"], s["status"], reconstruction=recon))
            else:
                title = {"core": "", "formulas": "핵심 수식", "example": "", "pitfalls": "헷갈리기 쉬운 부분"}[key]
                kind = KIND_OF[key] if not (key == "core" and cid == "C4") else "explanation"
                fig = None
                if key == "example" and cid == "C3":
                    fig = DEP_FIG
                if key == "example" and cid == "C2":
                    fig = SPAN_FIG
                blocks.append(block(kind, title, s["body_markdown"], s["refs"], s["status"], figure=fig))
            if key == "core":
                for proof in PROOFS.get(cid, []):
                    if proof["theorem_ref"]:
                        blocks.append(block("theorem", "", proof["statement"], [proof["theorem_ref"]], "observed"))
                        blocks.append(block("proof", "", proof["proof_markdown"], [proof["theorem_ref"]], "inferred", proof_method=proof["method"]))
                if cid == "C3":
                    blocks.append(block("recipe", "일차독립 판정", "1. 벡터들을 열로 세운 행렬 $A$를 만든다.\n2. $A\\mathbf{c} = \\mathbf{0}$을 행 줄인다.\n3. 자유변수가 없으면 일차독립, 있으면 일차종속.", ["P5"], "mixed"))
                    blocks.append(block("figure", "", "", ["P5"], "inferred", figure=TEST_FLOW))
        if cid == "C3":
            cx = PROOFS["C3"][1]
            blocks.append(block("proof", "반례: 평행하지 않아도 종속일 수 있다", cx["proof_markdown"], ["U1"], "inferred", proof_method="counterexample"))
        for key in SUPPORT_ORDER:
            s = secs.get(key)
            if s:
                blocks.append(block(KIND_OF[key], "", s["body_markdown"], s["refs"], s["status"]))
        entries.append({"concept_id": cid, "title": entry["title"], "depth": entry["depth"], "blocks": blocks})

    problems = []
    for cid in ("C2", "C3"):
        for i, item in enumerate(EXAM[cid]):
            if item["type"] == "true_false":
                continue
            problems.append({"id": f"문제 {len(problems) + 1}", "type": item["type"], "difficulty": item["difficulty"],
                             "prompt_markdown": item["prompt_markdown"], "answer_markdown": item["answer_markdown"],
                             "solution_markdown": item["solution_markdown"], "why_likely": item["why_likely"],
                             "refs": item["basis_refs"], "figure": None})
    v2 = {
        "schema": "math_study_note/2",
        "title": note["title"],
        "objectives": ["벡터들의 일차결합을 계산한다.", "span이 무엇을 모은 집합인지 설명한다.",
                       "일차독립의 정의를 영벡터와 계수로 말한다.", "벡터 묶음이 일차독립인지 판정한다."],
        "key_ideas": ["일차결합은 벡터를 상수배해 더한 것이다.", "span은 만들 수 있는 일차결합 전체의 집합이고, 부분공간이다.",
                      "일차독립은 영벡터를 만드는 계수가 모두 0인 것뿐이라는 뜻이다.", "영벡터가 들어 있으면 항상 일차종속이다."],
        "big_picture": note["big_picture"],
        "concept_order": note["concept_order"],
        "entries": entries,
        "summary": ["$c_1v_1 + \\cdots + c_kv_k = 0 \\Rightarrow c_1 = \\cdots = c_k = 0$이면 일차독립.",
                    "일차종속 ⇔ 어떤 벡터가 나머지의 일차결합이다.", "판정: 열로 세운 행렬의 동차방정식에 자유변수가 있는지 본다."],
        "exam": {"true_false": [
            {"statement_markdown": "영벡터를 포함한 벡터 묶음은 일차독립일 수 있다.", "answer": False,
             "explanation_markdown": "영벡터의 계수만 1로 두면 0이 아닌 계수로 영벡터가 만들어진다.", "refs": ["P4"]},
            {"statement_markdown": "span은 항상 부분공간이다.", "answer": True,
             "explanation_markdown": "영벡터를 포함하고 덧셈과 스칼라배에 닫혀 있다.", "refs": ["T1"]}],
            "problems": problems},
        "open_questions": note["open_questions"],
    }
    save("note_editor", v2)


if __name__ == "__main__":
    migrate_lesson()
    migrate_note()
    print("migrated")
