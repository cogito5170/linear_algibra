import copy
import unittest

from math_study_agent.agents import IntuitionTeacher, NoteEditor
from math_study_agent.agents.note_editor import board_block_issues
from math_study_agent.circuit_figures import schematic_svg, svg_text, terminals
from math_study_agent.figures import figure_issues
from math_study_agent.orchestrator import build_learning_contexts, build_report, deterministic_checks, render_html, render_markdown
from math_study_agent.schemas import validate
from math_study_agent.schemas.upgrade import note_v2_to_v3

from .helpers import fixtures


def _el(type_, points, label="", mirror=False, role="normal"):
    return {"type": type_, "points": [list(p) for p in points], "label": label, "mirror": mirror, "role": role}


def _figure(kind, **fields):
    figure = {"kind": kind, "title": "", "caption": "", "steps": [], "lines": [], "nodes": [], "edges": [],
              "elements": [], "x_label": "", "y_label": "", "series": [], "marks": []}
    figure.update(fields)
    return figure


def cascode():
    """NMOS cascode: M1 at (3,3) on top of M2 at (3,5), output port above M1."""
    return _figure("schematic", title="NMOS cascode", elements=[
        _el("nmos", [(3, 3)], "M_1"), _el("nmos", [(3, 5)], "M_2"),
        _el("wire", [(4, 2), (4, 1)]), _el("port", [(4, 1)]),
        _el("port", [(2, 3)], "V_{b1}"), _el("port", [(2, 5)], "V_{b2}"),
        _el("ground", [(4, 6)]), _el("arrow", [(4.7, 0.3), (4.7, 1.3)], "R_{out}"),
    ])


def _block(kind, body="M1이 전류를 고정하기 때문에 출력 저항이 커진다.", refs=("E1",), status="inferred", **extra):
    block = {"kind": kind, "title": "", "body_markdown": body, "refs": list(refs), "status": status,
             "figure": None, "reconstruction": None, "proof_method": None, "basis": None}
    block.update(extra)
    return block


class SchematicTest(unittest.TestCase):
    def test_transistor_terminals(self):
        self.assertEqual(terminals(_el("nmos", [(3, 3)])), [(4, 2), (2, 3), (4, 4)])
        self.assertEqual(terminals(_el("pnp", [(3, 3)], mirror=True)), [(2, 2), (4, 3), (2, 4)])
        self.assertEqual(terminals(_el("opamp", [(5, 5)])), [(4, 4.5), (4, 5.5), (6, 5)])

    def test_valid_cascode(self):
        self.assertEqual(figure_issues(cascode(), "f"), [])

    def test_loose_terminal_is_reported(self):
        figure = cascode()
        figure["elements"] = [e for e in figure["elements"] if e["type"] != "ground"]
        issues = figure_issues(figure, "f")
        self.assertTrue(any("(4, 6) is not connected" in i for i in issues), issues)

    def test_a_wire_tap_counts_as_connected(self):
        figure = _figure("schematic", elements=[
            _el("wire", [(1, 1), (5, 1)]), _el("resistor", [(3, 1), (3, 3)], "R"), _el("ground", [(3, 3)]),
            _el("port", [(1, 1)]), _el("port", [(5, 1)]),
        ])
        self.assertEqual(figure_issues(figure, "f"), [])

    def test_shape_rules(self):
        diagonal = _figure("schematic", elements=[_el("resistor", [(1, 1), (2, 2)])])
        self.assertTrue(any("horizontally or vertically" in i for i in figure_issues(diagonal, "f")))
        off_grid = _figure("schematic", elements=[_el("nmos", [(3.3, 3)])])
        self.assertTrue(any("0.5 grid" in i for i in figure_issues(off_grid, "f")))
        self.assertTrue(figure_issues(_figure("schematic"), "f"))

    def test_svg(self):
        svg = schematic_svg(cascode())
        self.assertTrue(svg.startswith('<svg class="sch"'))
        self.assertIn("V<tspan", svg)
        self.assertIn("<polygon", svg)  # source arrow and the R_out arrowhead

    def test_svg_text_sub_and_symbols(self):
        out = svg_text("r_{O2} \\parallel r_{\\pi 1}")
        self.assertIn('font-size="78%">O2</tspan>', out)
        self.assertIn("‖", out)
        self.assertIn("π 1", out)

    def test_plot(self):
        good = _figure("plot", x_label="V_{in}", y_label="I_D",
                       series=[{"label": "", "xs": [0, 1, 2], "ys": [0, 1, 4], "style": "solid"}], marks=[])
        self.assertEqual(figure_issues(good, "p"), [])
        bad = copy.deepcopy(good)
        bad["series"][0]["ys"] = [0, 1]
        self.assertTrue(figure_issues(bad, "p"))


class BoardBlockTest(unittest.TestCase):
    def test_rules(self):
        ok = _block("board", basis="교안 5쪽 A. 칸이 비어 있음")
        self.assertEqual(board_block_issues(ok, "b"), [])
        self.assertTrue(board_block_issues({**ok, "status": "observed"}, "b"))
        self.assertTrue(board_block_issues({**ok, "basis": None}, "b"))
        self.assertTrue(board_block_issues({**ok, "refs": []}, "b"))
        self.assertTrue(board_block_issues(_block("explanation", basis="x"), "b"))


class CircuitsDomainTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()
        self.contexts = build_learning_contexts(self.f["analysis"], self.f["concept_map"], self.f["bundle"])
        self.note = copy.deepcopy(self.f["note"])
        self.note["domain"] = "circuits"

    def failed(self, note):
        checks = deterministic_checks(note, self.f["lesson"], self.f["concept_map"], self.contexts)
        return {c["check_id"] for c in build_report(checks)["checks"] if not c["passed"]}

    def entry(self, cid):
        return next(e for e in self.note["entries"] if e["concept_id"] == cid)

    def test_upgrade_is_valid(self):
        old = copy.deepcopy(self.f["note"])
        old.pop("domain")
        old["schema"] = "math_study_note/2"
        for e in old["entries"]:
            for b in e["blocks"]:
                b.pop("basis")
                if b["figure"]:
                    for k in ("elements", "x_label", "y_label", "series", "marks"):
                        b["figure"].pop(k)
        for p in old["exam"]["problems"]:
            if p["figure"]:
                for k in ("elements", "x_label", "y_label", "series", "marks"):
                    p["figure"].pop(k)
        self.assertEqual(validate(old), [])
        self.assertEqual(note_v2_to_v3(old), self.f["note"])

    def test_board_block_must_be_labeled(self):
        self.entry("C2")["blocks"].append(_block("board", status="observed", basis="b"))
        self.assertIn("BD1.board_labeled", self.failed(self.note))

    def test_answers_need_units(self):
        problem = self.note["exam"]["problems"][0]
        self.note["exam"]["problems"] = [problem]
        problem["type"] = "computation"
        problem["answer_markdown"] = "$R_{out} \\approx 475$"
        self.assertIn("UN1.answer_units", self.failed(self.note))
        problem["answer_markdown"] = "$R_{out} \\approx 475\\,\\mathrm{k\\Omega}$"
        self.assertNotIn("UN1.answer_units", self.failed(self.note))

    def test_core_needs_reasons(self):
        for e in self.note["entries"]:
            for b in e["blocks"]:
                b["body_markdown"] = "결과는 다음과 같다."
        self.assertIn("CL1.causal_reasoning", self.failed(self.note))

    def test_rendered_with_circuit_names_and_figures(self):
        blocks = self.entry("C2")["blocks"]
        blocks.append(_block("board", basis="교안의 A. 칸", figure=cascode()))
        blocks.append(_block("proof", proof_method="small_signal"))
        page = render_html(self.note, self.f["concept_map"], self.contexts)
        self.assertIn("판서 복원 · 추정", page)
        self.assertIn("복원 근거", page)
        self.assertIn('<svg class="sch"', page)
        self.assertIn(">유도<", page)
        self.assertIn("소신호 등가회로", page)
        md = render_markdown(self.note, self.f["concept_map"], self.contexts)
        self.assertIn("**복원 근거**", md)

    def test_domain_prompt_is_added(self):
        self.assertIn("분야 규칙: 회로", NoteEditor(None, domain="circuits").system_prompt())
        self.assertNotIn("분야 규칙: 회로", IntuitionTeacher(None).system_prompt())
        with self.assertRaises(ValueError):
            NoteEditor(None, domain="biology")

    def test_editor_checks_domain_and_board(self):
        payload = {
            "schema": "math_note_request/3", "domain": "math", "title": "", "style_profile": {},
            "concept_map": self.f["concept_map"], "lesson": self.f["lesson"],
            "learning_contexts": self.contexts, "revision_feedback": [],
        }
        self.entry("C2")["blocks"].append(_block("board", basis=None))
        issues = NoteEditor(None).semantic_issues(self.note, payload)
        self.assertTrue(any("domain must be 'math'" in i for i in issues))
        self.assertTrue(any("needs a basis" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
