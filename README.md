# linear_algibra

## Math Study Agent System

교수님의 강의 교안과 수업 필기를 입력으로 받아, **교수님이 수업에서 설명하려던 개념의 흐름과 연결을 보존한 공부 노트**로 재구성하는 Multi-Agent 시스템입니다.

목표는 요약이 아닙니다. "수업을 놓쳤더라도 이 노트를 읽으면 교수님이 무엇을 설명하려 했는지 개념적으로 이해할 수 있는 상태"를 만드는 것입니다. 문제 풀이나 증명 생성은 목적이 아닙니다.

설명 방향은 *soft but logically correct*입니다. 직관적이고, 수식보다 개념이 먼저이며, 개념 사이의 관계와 "왜 배우는가?"를 분명히 합니다.

```text
                    Orchestrator
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
   Material Analyst -> Concept Mapper -> Intuition Teacher
                                             |
                                             v
                                        Note Editor
                                             |
                                             v
                                      Final Study Note
```

실제 실행 흐름(Orchestrator 기준):

```text
교안/필기 파일 ─► ingest (chunk + id) ─► math_material_bundle/1
  ─► Material Analyst ─► [근거 검증 guard] ─► math_material_analysis/1
  ─► Concept Mapper   ─► [근거 검증 guard] ─► math_concept_map/1
  ─► 개념별 math_learning_context/2 패킷 생성
  ─► Intuition Teacher ─► math_intuition_lesson/1
  ─► Note Editor       ─► math_study_note/1
  ─► Quality Check (결정적 검사 + LLM 검토) ─► 필요하면 Note Editor 재작성
  ─► Markdown 렌더링 ─► study_note.md
```

## 빠른 시작

아래 명령은 zsh/bash 그대로 붙여 넣어 실행할 수 있습니다. zsh는 기본 설정에서 대화형 셸의 `#` 주석을 인식하지 않고 `[ ]`를 파일 패턴으로 해석하므로, 명령 줄에 주석을 넣지 않고 `'.[llm,pdf]'`는 따옴표로 감쌌습니다.

설치 (anthropic SDK와 PDF 파서 포함):

```zsh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[llm,pdf]'
```

API 없이 예제 재생 (녹화된 agent 출력 사용):

```zsh
python3 -m math_study_agent run \
  --bundle examples/linear_independence/bundle.json \
  --replay examples/linear_independence/recorded \
  --out runs/demo
```

실제 실행 (`ANTHROPIC_API_KEY` 또는 `ant auth login` 필요):

```zsh
export ANTHROPIC_API_KEY='sk-ant-...'
python3 -m math_study_agent run \
  --slides lec03.pdf \
  --prof-notes board_notes.md \
  --handwritten handwritten_converted.txt \
  --user-notes my_notes.md \
  --title '3강. 일차결합, 생성(Span), 일차독립' \
  --out runs/lec03
```

결과는 `runs/lec03/study_note.md`에 생기고, 각 단계의 JSON(`analysis.json`, `concept_map.json`, `learning_contexts.json`, `lesson.json`, `note.json`, `quality_report.json`), 실행 기록(`manifest.json`), 모델 요청/응답 원문(`llm/`)이 함께 저장됩니다.

예제의 실제 출력은 [`examples/linear_independence/output/study_note.md`](examples/linear_independence/output/study_note.md)에서 볼 수 있습니다.

종료 코드: `0` 노트 완성, `2` 노트는 만들었지만 품질 검사 오류가 남아 **검토 필요**, `1` 실패.

기타 명령 (순서대로: chunk id 확인, 아무 payload나 schema 검사, JSON Schema 내보내기):

```zsh
python3 -m math_study_agent ingest --slides lec03.pdf --out bundle.json
python3 -m math_study_agent validate runs/lec03/concept_map.json
python3 -m math_study_agent schemas schemas/
```

주요 옵션: `--model`(기본 `claude-opus-5-5`), `--effort`(기본 `high`), `--max-attempts`(agent별 재시도, 기본 2), `--max-revisions`(품질 검사 후 재작성 횟수, 기본 1), `--no-reviewer`, `--no-fallbacks`, `--handwritten-author professor|user|unknown`.

## 구성 요소

| 구성 요소 | 파일 | 입력 schema | 출력 schema |
|---|---|---|---|
| Material Analyst | `agents/material_analyst.py` | `math_material_bundle/1` | `math_material_analysis/1` |
| Concept Mapper | `agents/concept_mapper.py` | `math_concept_mapping_request/1` | `math_concept_map/1` |
| Intuition Teacher | `agents/intuition_teacher.py` | `math_teaching_request/1` | `math_intuition_lesson/1` |
| Note Editor | `agents/note_editor.py` | `math_note_request/1` | `math_study_note/1` |
| Quality Reviewer (Orchestrator 소속) | `orchestrator/quality.py` | `math_review_request/1` | `math_quality_review/1` |
| Orchestrator | `orchestrator/orchestrator.py` | | `math_quality_report/1`, Markdown |

- **Prompt**: `math_study_agent/prompts/`. 모든 agent가 공통 원칙(`shared_principles.md`: 근거 상태, 금지 사항, 수학적 정확성)을 받고, 설명을 쓰는 agent는 스타일 가이드(`shared_style.md`: "직관적"의 정의, 설명 순서, 문체, 난이도 정책)를 추가로 받습니다.
- **Schema**: `math_study_agent/schemas/definitions.py`에 정의, `schemas/*.json`으로 내보낸 사본이 있습니다 (테스트가 동기화를 확인).
- **LLM backend**: `llm/`. Agent는 `LLMClient` 인터페이스만 알고 SDK를 직접 부르지 않습니다. `AnthropicLLM`(실제), `ReplayLLM`(녹화 재생), `ScriptedLLM`(테스트), `RecordingLLM`(요청/응답 저장)이 있습니다.
- **Ingest**: `ingest/loaders.py`. `.md`/`.txt`/`.pdf`를 페이지·섹션 정보가 붙은 chunk로 나누고 `slides#004` 같은 id를 붙입니다.

## Semantic contract

Agent 사이 통신은 모두 버전이 붙은 JSON입니다 (`"schema": "math_concept_map/1"`). 모든 object는 닫혀 있고(`additionalProperties: false`) 모든 필드가 필수입니다. 값이 없으면 `null`이나 빈 배열을 씁니다. 같은 schema가 jsonschema 검증, 문서, 그리고 모델의 structured output 제약(`output_config.format`)에 그대로 쓰입니다. 구조화 출력이 지원하지 않는 제약(`minLength`, `pattern`, `minimum` 등)은 전송 시 빠지고 클라이언트에서 검증됩니다.

**버전 규칙**: 공개된 schema는 깨지 않습니다. 새 형태가 필요하면 버전을 올립니다. 예: 기본 계약 `math_learning_context/1`은 명세 그대로 유지하고, 파이프라인은 하위 호환 확장인 `math_learning_context/2`(정리 `theorems`, 전체 근거 위치 `sources`, `role`, `prerequisites`, `leads_to`, `open_questions` 추가)를 사용합니다. `to_v1()`로 v1 계약에 맞게 투영할 수 있습니다.

## Hallucination control

모든 추출·해석 항목은 `status`(`observed` / `inferred` / `uncertain`), `confidence`, `evidence`(chunk id + 원문 그대로의 인용), `rationale`을 가집니다.

Orchestrator는 모델의 말을 믿지 않고 확인합니다.

1. **인용 검증 guard**: 모든 `evidence.quote`가 해당 chunk 원문에 실제로 있는지 문자열로 확인합니다 (공백·마크다운 차이만 허용). 확인되지 않은 근거는 버리고, 근거가 남지 않은 `observed` 항목은 `uncertain`으로 낮춥니다.
2. **교수님 발언 보호**: `professor_emphasis`는 검증된 `observed`만 남습니다. 추측이거나 근거가 확인되지 않은 "교수님 강조"는 `uncertainties`로 옮겨집니다. 학생 필기에만 근거가 있으면 `user_reported`로 표시되고 노트에 "내 필기 기록"으로 출처가 붙습니다.
3. **참조 무결성**: 이후 agent는 존재하는(검증을 통과한) id만 인용할 수 있습니다. Teacher가 해당 개념의 professor context에 없는 P id를 인용하거나, 교안 수식이 아닌 것을 교안 수식(`origin: material`)으로 표시하면 출력이 거부됩니다. 교안에 없는 수식은 `supplementary`로 표시되고 노트에 "보충: 교안에 없는 수식"으로 나타납니다.
4. **노트 표시**: 추론이 섞인 섹션 제목에는 `[추론]`, `[불확실]`, `[자료+추론]`이 붙고, 교수님 섹션 아래에는 근거 위치(`slides p.4` 등)가 붙습니다. 확인하지 못한 부분은 "아직 확인이 필요한 부분"에 모입니다.

guard가 바꾼 모든 것은 품질 보고서에 기록됩니다. 조용히 고치지 않습니다.

## 실패 처리

- Agent 입력은 호출 전에 schema 검증합니다.
- Agent 출력은 schema 검증 + 의미 검증(id 참조, 학습 순서와 선수 개념, 순환 의존, 모든 개념 포함 여부 등)을 거칩니다. 실패하면 오류 목록을 피드백으로 주고 재시도하며, 끝내 실패하면 `AgentError` → `PipelineError`로 중단합니다. 실패한 출력이 다음 단계로 넘어가는 일은 없습니다.
- 모델 거절(refusal)은 재시도하지 않습니다. 잘린 출력(max_tokens)이나 잘못된 JSON은 재시도합니다. 실제 호출은 서버 측 refusal fallback(`fallbacks: "default"`)을 기본으로 켭니다 (`--no-fallbacks`로 끌 수 있음).
- 실패해도 `manifest.json`에 어느 단계에서 왜 실패했는지와 시도 기록이 남습니다.
- LLM 품질 검토자가 실행되지 못하면 "통과"가 아니라 오류(`RV.unavailable`)로 기록됩니다.

## 최종 품질 검사

| 범주 | 결정적 검사 (항상) | LLM 검토자 |
|---|---|---|
| Source fidelity | 교수님 언급에 검증된 P 근거가 있는가, 보충 수식 표시, 자료의 불확실성이 노트에 드러나는가, 추론된 동기를 observed로 표시하지 않았는가 | 자료에 없는 내용을 사실처럼 썼는가 |
| Conceptual clarity | 핵심 개념이 full로 다뤄지고 한 줄 직관/핵심 개념 섹션이 있는가, 모든 개념이 등장하는가 | 핵심과 관계가 분명한가 |
| Intuition | 핵심 개념에 "왜 배우는가?"가 있는가, 수식 앞에 의미 설명이 있는가 | "왜?"가 실제로 답해졌는가 |
| Logicality | 선수 개념이 먼저 나오는가, learning flow 순서를 따르는가 | 갑자기 등장하는 개념/기호가 없는가 |
| Mathematical correctness | | 정의·조건·⇒/⇔·근사·존재/유일성이 보존되었는가 |
| User readability | 평균 문장 길이, 보조 개념의 과도한 섹션 분할 | 어려운 용어, 의미 없는 비유 |

`error`가 남으면 Note Editor에 피드백을 주고 다시 쓰게 합니다(`--max-revisions`). 그래도 남으면 노트 맨 위에 **검토 필요** 경고가 붙고 종료 코드 2로 끝납니다.

## 테스트

```zsh
python3 -m unittest discover -s tests -t .
```

pytest가 설치되어 있으면 `pytest`로도 실행됩니다.

테스트는 API 호출 없이 녹화된 예제와 scripted backend로 다음을 확인합니다: 모든 schema의 유효성과 structured-output 호환성, 예제 전체 파이프라인, 재시도와 피드백, 실패 시 중단과 기록, 근거 검증 guard(조작된 인용, 근거 없는 교수님 강조, 출처 재귀속), 각 agent의 의미 검증, 품질 검사와 재작성 루프, 렌더링, Anthropic backend의 요청 형태와 오류 처리, CLI.

## 구현 단계

- **Phase 1** (완료): Orchestrator, Material Analyst, Concept Mapper, Intuition Teacher, Note Editor
- **Phase 2** (완료): source tracking(chunk id, 페이지, 섹션), confidence, observed/inferred/uncertain, schema validation, 인용 검증 guard
- **Phase 3** (일부): 텍스트 PDF 파싱(`pdfplumber` 또는 `pypdf`) 완료. 손필기 OCR, 수식 이미지 추출, 여러 강의 사이 개념 연결, 복습 모드는 아직 없습니다. 손필기는 텍스트로 변환해서 `--handwritten`으로 넣어야 하고, 스캔 PDF는 텍스트가 추출되지 않아 오류가 납니다.
