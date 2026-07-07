# Fable Harness

> Claude Code(Opus / Sonnet / Haiku)를 규율 있는 엔지니어처럼 일하게 만드는, 바로 적용 가능한 행동 프로토콜——뛰어들기 전에 먼저 살피고, 가정을 소리 내어 말하고, 큰 결론을 믿기 전에 제3자에게 검증받고, 진짜 테스트로 결과를 증명한다.

[English](README.md) &nbsp;·&nbsp; [繁體中文](README.zh-TW.md) &nbsp;·&nbsp; [简体中文](README.zh-CN.md) &nbsp;·&nbsp; [日本語](README.ja.md) &nbsp;·&nbsp; **한국어**

![Version: 1.0.0](https://img.shields.io/badge/version-1.0.0-blue.svg) &nbsp; ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## 이것은 무엇인가

Fable Harness는 작은 키트——몇 개의 hook, 하나의 skill, 몇 개의 서브에이전트——로, Claude Code 세션을 열 때마다 자동으로 주입됩니다. Claude에게 새로운 재주를 가르치는 것이 아니라, Claude가 **매번 규율 있는 프로세스를 따르도록** 보장합니다. 답하기 전에 증거를 모으고, 추측 대신 가정을 말하고, 자신의 큰 결론을 믿기 전에 스스로 반박하며, 변경이 정말로 작동한다는 것을(“괜찮아 보인다”가 아니라) 진짜 증거로 보여 줍니다.

이것은 프레임워크가 아니라 “행동의 하한선”이라고 생각하세요. 스프린트를 계획하거나 CI 파이프라인을 돌리지는 않습니다——에이전트가 작업하는 동안 정직하고, 신중하며, 검증 가능한 상태로 유지하는 것이 전부입니다.

## 왜 만들었나

이 키트는 Fable(Anthropic의 Fable 모델)의 두 번째 공개 버전에서 정제한 것으로, 그 모델이 작업에 임했던 신중하고 규율 있는 방식을 추출했습니다. 그 규율을 하나의 모델 안에 가둬 두는 대신, 재사용 가능한 프로토콜로 뽑아내어 Opus(및 다른 Claude 모델) 주변의 작업 하네스를 보강합니다. 그래서 어떤 모델이 주도하든, 세션을 거듭해도 같은 규율로 동작합니다.

한계도 솔직히 말해 둡니다. hook과 skill이 이식할 수 있는 것은 *절차*(먼저 관찰하기, 가정 말하기, 결론을 교차 심문하기, 검증 증거 요구하기)뿐이며, 모델이 타고난 판단력은 이식할 수 없습니다. 하지만 실제로 “좋은” 에이전트와 “대충 하는” 에이전트의 차이 대부분은 판단력 부족이 아니라 절차를 건너뛰는 데서 옵니다. 이 키트가 메우는 것이 바로 그 차이입니다.

## 어떻게 작동하나

- **OODA 루프**——답하기 전에 Claude는 증거를 모으고(실제 파일을 검색·읽으며 훈련 기억으로 추측하지 않음), 가정을 말하고, 과제를 검증 가능한 목표로 바꾼 뒤(“작동만 하면 된다”는 부족함), 작게 고치고 매 단계를 확인합니다.
- **다자 대립 리뷰(adversarial review)**——이 키트의 대표 기능. 큰 결론(아키텍처 결정, 근본 원인 진단, 프로덕션에 영향을 줄 수 있는 모든 것)을 믿기 전에, Claude는 3개의 독립적인 “반대” 서브에이전트를 *동시에* 파견합니다. 각자 역할이 다르며, **skeptic**은 논리적 허점을, **red-team**은 보안과 장애 위험을, **simplifier**는 불필요한 과잉 설계를 찾습니다. 셋 중 과반이 “살아남아야” 그 결론이 채택됩니다.
- **모델 배분**——추론·아키텍처·근본 원인 작업은 현재 주도하는 모델에 남기고, 코딩과 리팩터링은 Sonnet에, 일괄 파일 처리·검색·텍스트 정리는 Haiku에 맡깁니다. 일에 알맞은 크기의 모델을 씁니다.
- **완료의 정의(Definition of Done, TDD)**——실제 로직을 건드리는 변경에는 자동화 테스트와 “수정 전에는 테스트가 실패하고 수정 후에는 통과한다”는 증거가 필요합니다. 출력을 눈으로 보거나 아무 데나 `console.log`를 찍는 것은 검증으로 인정하지 않습니다.
- **정직한 보고**——모든 보고의 첫 문장은 실제 결과(서론이 아니라)이며, 실패는 실패로 보고하고 미화하지 않습니다.

## 안에 무엇이 들어 있나

| 구성 요소 | 파일 | 역할 |
|---|---|---|
| 행동 프로토콜 | `.claude/hooks/fable_protocol.md` + `inject_protocol.sh` | 각 세션 시작 시 주입 |
| 매 턴 짧은 리마인드 | `.claude/hooks/prompt_nudge.sh` | 사용자의 각 메시지에 한 줄 리마인드를 주입 |
| 검증 게이트 | `.claude/hooks/verify_gate.py` | 이번 턴에 코드를 바꿨는데 테스트를 돌리지 않았다면 턴 종료를 한 번 차단(두 번째는 통과) |
| 대립 리뷰 | `.claude/skills/adversarial-review/` | 위의 세 반대역 리뷰 흐름을 정의하는 skill |
| 반대역 에이전트 | `.claude/agents/{skeptic,red-team,simplifier}.md` | 대립 리뷰에 쓰이는 3개의 독립 서브에이전트 역할 |
| 모델 배분 | `CLAUDE.md` | 위에서 설명한 배분 표 |
| harness 감지기 | `scripts/detect_harness.py` | 읽기 전용 확인——프로젝트에 이미 자체 개발 harness(예: harnessmith, Superpowers)가 있는지 확인하고, 있으면 Fable은 한 발 물러나 하한선만 담당 |
| 거버넌스 문서 | `diagnostics.md`, `model_dispatch_rules.md`, `cognitive_rubrics.md`, `future_session_letter.md` | 알려진 장애 모드, 서브에이전트 파견 템플릿, 언제 속도를 늦출지에 대한 기준, 세션 간 인수인계 메모 |

## 빠른 시작

이 저장소를 clone한 뒤, 당신의 Claude Code에게 이렇게 말하세요: **“INSTALL.md를 따라 Fable Harness를 설치해 줘.”** Claude가 스스로 가이드를 읽고 안전하게(먼저 백업, 기존 설정은 절대 덮어쓰지 않음) 설치합니다. 구체적인 내용은 [INSTALL.md](INSTALL.md)를 참고하세요.

## 버전 규칙

이 키트는 [시맨틱 버저닝(Semantic Versioning)](https://semver.org/lang/ko/)을 따르며, `MAJOR.MINOR.PATCH` 형식으로 **1.0.0**부터 시작합니다:

- **MAJOR**——프로토콜 계약의 파괴적 변경(hook／skill／agent 제거·개명, 또는 프로토콜 주입 방식이나 에이전트 파견 방식의 비호환 변경). 사용자는 재설치나 설정 변경이 필요합니다.
- **MINOR**——하위 호환 추가(새로운 hook, skill, agent, 거버넌스 규칙). 기존 설치는 그대로 계속 작동합니다.
- **PATCH**——하위 호환 수정이나 표현 조정(hook 버그 수정, 규칙 명확화, 오타).

현재 버전은 [VERSION](VERSION)에 기록하고, 주요 변경 사항은 [CHANGELOG.md](CHANGELOG.md)에 기록합니다.

## 라이선스

MIT — [LICENSE](LICENSE) 참고(번역본: [繁體中文](LICENSE.zh-TW)).
