# 모빌리티 데일리 브리핑 — 실행 플레이북

이 문서는 **매일 자동으로 실행되는 Claude 세션**이 따라야 하는 절차입니다.
(Routine: "모빌리티 데일리 브리핑" — 매일 08:00 KST 발화)

## 중요: Bash/`git`을 절대 사용하지 않는다

이 자동화는 사람이 지켜보지 않는 상태로 실행됩니다. **Bash로 `git clone`/`git push` 등을
실행하면 최초 1회 사람 승인이 필요해 그 자리에서 영원히 멈춥니다** (실제로 두 번 재현
확인됨). 반면 GitHub MCP 도구(`mcp__github__*`)는 승인 없이 즉시 실행됩니다. 그래서 이
플레이북은 **처음부터 끝까지 GitHub API 도구 + Artifact 도구 + WebSearch + PushNotification만
사용**하고, Bash는 절대 호출하지 않는다. (`scripts/generate_dashboard.py`를 `python3`로
실행하는 것도 Bash이므로 자동화에서는 사용하지 않는다 — 이 스크립트는 사람이 로컬에서 수동
실행할 때만 쓴다.)

## 실행 순서

1. **현재 DB 읽기** — `mcp__github__get_file_contents`로 `main` 브랜치의
   `data/mobility_news.json`을 읽는다. 응답에 포함된 파일 SHA를 기억해 둔다 (나중에
   `create_or_update_file`에 필요).

2. **뉴스 수집** — `WebSearch`로 최근 24~48시간 내 모빌리티 뉴스를 검색한다. 최소 아래
   쿼리들을 실행하고, 필요하면 당일 이슈에 맞춰 쿼리를 추가한다:
   - `모빌리티 뉴스 오늘 자율주행 전기차 UAM`
   - `국내 자율주행 로보택시 뉴스`
   - `mobility industry news today autonomous EV robotaxi`
   - `UAM 도심항공교통 뉴스`
   - `전기차 배터리 뉴스`
   - (선택) 그날 화제가 된 특정 기업/이슈 키워드

   **검색 결과가 SEO성 종합 요약 페이지나 오래된 주간 칼럼 위주로만 나오면**, 아래처럼
   기간을 더 명시하거나 실제 언론사 도메인을 넣어 재검색해서 진짜 최근 기사를 찾는다:
   - `모빌리티 자율주행 뉴스 어제`, `TechCrunch mobility this week` 등 기간 표현 추가
   - `site:techcrunch.com`, `site:hankyung.com`, `site:etnews.com` 등 언론사 한정 검색

   **엄격한 신선도 기준 (중요)**: 이렇게 재검색까지 해봐도 실제 발행일이 대략 1~2일 이내인
   기사가 없으면, **오래된 기사로 채우지 않는다.** `date`가 오래된 기사를 `collected_at`만
   오늘로 바꿔치기해서 넣는 것은 금지 — 사용자가 이미 이 방식으로 "매일 갱신되는 것처럼
   보이지만 실제로는 오래된 기사만 쌓인다"는 문제를 지적한 바 있다. 진짜 최근 기사가
   하나도 없는 날은 **0건 추가가 정상**이며, 억지로 채우는 것보다 정직하게 0건으로
   끝내는 쪽이 낫다.

3. **선별 및 요약** — 검색 결과 중 아래 기준으로 5~15건을 고른다:
   - 실제 뉴스 기사/보도자료 (블로그·광고성 콘텐츠 제외)
   - 1번에서 읽은 `articles` 배열에 **이미 있는 URL과 중복되지 않는** 것
     (`url` 필드가 dedup 기준 키)
   - **발행일이 대략 1~2일 이내(엄격 기준)** — 오래된 기사는 아무리 관련성이 높아도
     제외한다
   - 국내 중심 + 주요 글로벌 이슈를 균형 있게 포함
   - 각 기사는 **1~2문장, 사실 위주 한국어 요약** 작성 (과장/추측 금지)

   조건을 만족하는 기사가 하나도 없으면(흔할 수 있음 — 이 검색 도구는 당일 실시간 뉴스
   색인이 약하다) 4~9단계를 건너뛰고 11번으로 간다 (커밋/PR 없이 종료, 0건 추가는 실패가
   아니라 정상 결과).

4. **분류** — `data/schema.md`에 정의된 카테고리 중 하나를 부여한다:
   `자율주행 | UAM | 전기차·배터리 | 모빌리티 서비스 | 정책·규제 | 기타`
   지역은 `국내 | 글로벌` 중 하나.

5. **DB 갱신 (메모리상에서)** — 1번에서 읽은 JSON의 `articles` 배열 끝에 새 항목을
   append한다 (기존 항목 수정 금지). 발행일을 URL/본문에서 확인할 수 없으면 `date`를
   수집일로 채우고 `date_estimated: true`로 표시한다. `updated_at`도 현재 시각(KST,
   ISO8601)으로 갱신한다. 이 전체 JSON을 문자열로 만들어 둔다 (8번에서 사용).

6. **대시보드 HTML 갱신 (메모리상에서)** — `mcp__github__get_file_contents`로 `main`의
   `artifact/dashboard.html`을 읽는다 (SHA도 기억). 아래 세 구간을 텍스트 치환한다
   (스크립트 실행 없이 직접 문자열 치환):
   - `<!--GENERATED_AT_START-->...<!--GENERATED_AT_END-->` 사이를 현재 시각
     (`YYYY-MM-DD HH:MM KST`)으로 교체
   - `<!--TOTAL_COUNT_START-->...<!--TOTAL_COUNT_END-->` 사이를 갱신된 articles 배열의
     총 개수로 교체
   - `/*ARTICLES_JSON_START*/...​/*ARTICLES_JSON_END*/` 사이를 5번에서 만든 전체 articles
     배열의 JSON 문자열로 교체 (배열 앞뒤 대괄호 포함, 다른 부분은 절대 건드리지 않는다)

7. **브랜치 생성** — `mcp__github__create_branch`로 `main` 기준
   `data-sync/YYYY-MM-DD` 브랜치를 만든다.

8. **파일 반영** — `mcp__github__create_or_update_file`로 아래 두 파일을 7번 브랜치에
   각각 커밋한다 (각 파일의 `sha`는 1번/6번에서 읽은 값 사용):
   - `data/mobility_news.json` (5번에서 만든 전체 JSON)
   - `artifact/dashboard.html` (6번에서 만든 전체 HTML)
   커밋 메시지 예: `데일리 브리핑: YYYY-MM-DD (N건 추가)`

9. **PR 생성 & 즉시 자동 병합** — `mcp__github__create_pull_request`로
   `data-sync/YYYY-MM-DD` → `main` PR을 만들고, 곧바로
   `mcp__github__merge_pull_request`(`merge_method: "squash"`)로 병합한다. 사람의 승인을
   기다리지 않는다 — 이 저장소의 데이터 파이프라인은 PR을 사람 리뷰용이 아니라 main 반영
   수단으로만 사용하도록 사용자와 합의되어 있다.

10. **아티팩트 재배포** — Artifact 도구로, 병합 후 6번에서 만든 최신 HTML 내용을
    **기존 대시보드와 같은 URL**로 재배포한다 (`url` 파라미터에 아래 URL 지정). favicon은
    항상 🚗로 유지한다.

    > 대시보드 URL: `https://claude.ai/code/artifact/688798f0-9f72-4476-b4f9-119c130b689a`

11. **푸시 알림** — `PushNotification` 도구로 오늘 추가된 기사 수와 헤드라인 1건을 한 줄로
    요약해 알린다. 예: `모빌리티 브리프: 오늘 6건 추가 (로보택시 규제 완화 등) → 대시보드 갱신 완료`
    (3번에서 추가할 기사가 없어 건너뛴 경우, 짧게 "오늘은 신규 기사 없음"으로 알린다.)

12. **실패 시** — 검색이 실패하거나 GitHub API 호출이 실패하면(예: 충돌) 무리하게 재시도하지
    말고 실패 사실을 `PushNotification`으로 짧게 알리고 종료한다.

## 하지 말 것

- **Bash 도구 호출 자체를 하지 않는다** (git, python3 포함 — 승인 대기로 영구 정지된다)
- 기존 기사 항목 삭제/수정 (오탈자 수정 등 명백한 오류 정정은 예외)
- 카테고리 값 임의 추가 (대시보드 색상 매핑이 고정 6종에 의존)
- 사실 확인 없는 추측성 요약, 광고성 문구
- `artifact/dashboard.html`의 마커 구간 밖 텍스트/코드를 임의로 변경
