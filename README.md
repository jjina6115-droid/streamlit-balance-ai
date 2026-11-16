# 밸런스 AI — Streamlit(파이썬) 버전

화면과 서버가 모두 **파이썬(Streamlit)** 으로 되어 있어요. 기능은 Netlify 버전과 같아요.

- **AI 훈련소 (6단계):** 규칙 → 순서도 → 질문 10개 → 0/1 기록 → 결과(CSV) → 광장에 올리기
- **AI 광장:** 💬 댓글(개선 체크), 대화하기, 👍👎, 6초마다 실시간 새로고침
- **반별로 따로:** 반마다 입장 비밀번호가 달라요. 학생은 자기 반 모둠과 자기 반 광장만 봐요.
- **비밀번호:** 처음 설정, 반 입장 비밀번호, 선생님 메뉴

**Netlify 버전과 다른 점:** AI 훈련소에 **모둠 이름 + 모둠 비밀번호**로 들어가요. 쓴 내용이 서버에 모둠별로 저장돼서, 다른 날 다른 컴퓨터에서 들어와도 이어서 할 수 있어요. 모둠 비밀번호를 잊으면 선생님 메뉴에서 다시 정해 줄 수 있어요.

---

## 올리는 순서 (처음 한 번)

### 1. Supabase 준비하기 (추천, 5분)

Streamlit Cloud는 앱이 다시 시작되면 앱 폴더의 파일이 지워져요. 그래서 모둠 작업, 광장, 댓글을 **Supabase(무료 온라인 저장소)** 에 저장하는 걸 추천해요.

1. supabase.com에 가입하고 **New project**를 만들어요. Region은 Seoul을 골라요.
2. 왼쪽 메뉴 **SQL Editor**에 아래를 붙여 넣고 **Run**을 눌러요.

```sql
create table if not exists balance_kv (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);
alter table balance_kv enable row level security;
```

3. **Project Settings**에서 두 가지를 복사해 둬요.
   - **Project URL** (`https://○○○.supabase.co`)
   - **secret 키** (`sb_secret_…`, 예전 화면에서는 `service_role` 키)
   - ⚠️ publishable(anon) 키가 아니라 **secret 키**예요. 이 키는 Streamlit Secrets에만 넣고 다른 곳에 올리지 마세요.

> Supabase 없이 올려도 동작해요. 다만 앱이 다시 시작되면(GitHub 파일을 고칠 때 등) 데이터가 지워질 수 있어요.

### 2. GitHub에 올리기

1. github.com → 오른쪽 위 **+** → **New repository**를 눌러요. 이름 예: `balance-ai-python`, **Private**.
2. **uploading an existing file**을 눌러요.
3. 압축을 푼 폴더 **안에서** 아래를 모두 선택해 끌어다 놓고 **Commit changes**를 눌러요.
   - `streamlit_app.py`, `requirements.txt`, `README.md`, `balance` 폴더, `.streamlit` 폴더
4. 저장소 첫 화면에 `streamlit_app.py`가 **바로 보여야** 해요. 폴더 하나만 보이면 잘못 올라간 거예요.

> `.streamlit` 폴더는 색 설정이에요. 안 보이거나 빠져도 앱은 동작해요. (Mac에서는 Finder에서 Cmd+Shift+. 를 누르면 보여요)

### 3. Streamlit Community Cloud에 배포하기

1. share.streamlit.io에 가서 **Continue with GitHub**로 로그인해요.
2. **Create app** → GitHub에 있는 앱 배포를 골라요.
3. 아래처럼 채워요.
   - **Repository**: 방금 만든 저장소
   - **Branch**: `main`
   - **Main file path**: `streamlit_app.py`
   - **App URL**: 원하는 이름 (예: `balance-ai-2-3`)
4. **Advanced settings**를 열고 **Secrets** 칸에 아래를 붙여 넣어요. 따옴표 안을 내 값으로 바꿔요.

```toml
SUPABASE_URL = "https://○○○.supabase.co"
SUPABASE_KEY = "sb_secret_…"

# (선택) 아래 두 줄을 넣으면 '처음 설정' 화면 없이 바로 시작해요. (반은 선생님 메뉴에서 만들어요)
# OPENAI_API_KEY = "sk-..."
# ADMIN_PASSWORD = "선생님비밀번호"
```

5. **Deploy**를 누르고 1~3분 기다려요.

### 4. 처음 설정하고 학생들에게 나눠 주기

1. 배포된 주소(`○○○.streamlit.app`)를 열면 **처음 설정** 화면이 나와요. **학생들에게 알려 주기 전에** 바로 해 주세요. 먼저 연 사람이 비밀번호를 정하게 돼요.
2. 아래를 넣어요.
   - **AI API 키** (OpenAI `sk-…`)
   - **첫 번째 반 이름과 그 반 입장 비밀번호** (예: 2학년 3반 / 학생들에게 알려 줄 비밀번호)
   - **선생님 비밀번호** (학생들에게는 알려 주지 마세요)
3. 주소와 **우리 반 입장 비밀번호**를 학생들에게 알려 줘요. 한 번 들어온 기기는 새로고침해도 다시 묻지 않아요.

## 여러 반에서 쓰기

- **선생님 메뉴 → 반 관리 → 새 반 만들기**에서 반 이름과 그 반 입장 비밀번호를 정해요. 반마다 비밀번호가 달라야 해요.
- 학생이 입장 비밀번호를 넣으면 **그 비밀번호의 반**으로 들어가요. 자기 반 모둠과 자기 반 광장만 보여서, 반이 달라도 모둠 이름(예: 1모둠)이 겹치지 않아요.
- 7~8차시처럼 며칠에 걸쳐 해도 반마다 기록이 그대로 남아요. 초기화할 필요가 없어요.
- 선생님은 **이 반 보기**를 눌러 그 반의 훈련소와 광장을 볼 수 있어요. 입장 화면에서 선생님 비밀번호를 넣어도 들어와요.
- **결과 CSV:** 반의 모든 모둠의 기준별 지킨 개수(가장 최근 차수)를 한 파일로 받아요.
- **반 지우기:** 그 반의 모둠 작업·평가 기록·광장 AI·댓글을 모두 지워요. 지우기 전에 결과 CSV를 받아 두세요.
- 반 기능 전에 쓰던 데이터가 있으면 처음 한 번 **'우리 반'** 으로 옮겨져요. 원래 쓰던 입장 비밀번호가 '우리 반'의 비밀번호가 돼요. 반 이름은 선생님 메뉴의 '이름·비밀번호 바꾸기'에서 바꿀 수 있어요.

## 선생님 혼자 시험해 보기 (Gemini 무료 키)

OpenAI 결제 전에 선생님 혼자 시험해 볼 때만 써요. Gemini 약관상 18세 미만이 쓰는 앱에는 쓸 수 없어요.
1. aistudio.google.com/apikey 에서 키(`AQ.…`)를 받아요.
2. Streamlit Secrets에 `OPENAI_API_KEY = "AQ.…"` 를 넣거나, 처음 설정·선생님 메뉴의 키 칸에 넣어요.
3. 수업 전에 선생님 메뉴에서 OpenAI 키(`sk-…`)를 넣으면 OpenAI로 바뀌어요.

---

## 선생님 메뉴 (위쪽 메뉴의 "선생님")

선생님 비밀번호로 들어가면 아래를 할 수 있어요.
- **반 관리:** 반 만들기, 이 반 보기, 이름·비밀번호 바꾸기, 결과 CSV, 반 지우기
- AI 키, 선생님 비밀번호 바꾸기
- **모둠 관리 (지금 보는 반):** 모둠 비밀번호 다시 정하기, 모둠 지우기
- **광장 관리:** 모든 AI에 '내리기', 모든 댓글에 '지우기' 버튼이 보여요.

## 알아 둘 점

- **API 키:** 키는 서버(Supabase 또는 Streamlit Secrets)에만 있고 학생 화면으로 보내지 않아요.
- **비밀번호:** 그대로 저장하지 않고, 풀 수 없게 바꾼 값만 저장해요.
- **잠든 앱:** 앱을 한동안 아무도 안 쓰면 잠들어요. 주소를 열었을 때 깨우는 버튼이 보이면 누르고 1분쯤 기다려요. 수업 전에 미리 한 번 열어 두세요.
- **비용:** 평가 질문 1개 = OpenAI 호출 1번, 대화 1번 = 호출 1번이에요. OpenAI에서 월 사용 한도를 꼭 걸어 두세요.
- **CSV 파일:** 첫 줄에는 "모둠명"과 모둠 이름이, 그 아래에는 기준 5가지와 기준마다 지킨 개수(1의 개수)가 들어가요.
- **평가 기준 바꾸기:** `balance/shared.py`의 `CRITERIA` 부분을 고쳐요. (5개 그대로)
- **고치고 싶을 때:** GitHub에서 파일을 고치고 Commit하면 Streamlit이 1~2분 안에 알아서 다시 시작해요. Supabase를 쓰면 데이터는 그대로예요.

## 내 컴퓨터에서 실행해 보기 (선택)

파이썬 3.10 이상이 필요해요. 명령창에서 이 폴더로 이동한 뒤 아래를 실행해요.

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

브라우저에서 `http://localhost:8501`이 열려요. 이때 데이터는 이 폴더의 `balance_data.db` 파일에 저장돼요.

## 파일 구조

```
streamlit_app.py       시작 파일 (비밀번호 확인 → 위쪽 메뉴: 처음 · AI 훈련소 · AI 광장 · 선생님)
requirements.txt       필요한 부품 (streamlit, requests, pandas)
.streamlit/config.toml 색 설정
balance/
  shared.py    안전 원칙, 순서도를 AI에게 전하는 문장, 평가 기준 5가지, 아이디어 카드
  ai.py        AI 부르기 (OpenAI, 시험용 Gemini)
  store.py     저장소 (Supabase 또는 balance_data.db 파일)
  data.py      모둠 작업 · 광장의 AI · 댓글 읽고 쓰기 (반마다 따로)
  auth.py      처음 설정, 반과 반 입장 비밀번호, 선생님 비밀번호
  ui.py        디자인(모눈종이 바탕, 남색 글자), 순서도 그림
  home.py      처음 화면
  studio.py    AI 훈련소 6단계
  plaza.py     AI 광장 (목록, 💬 댓글 창, 대화 화면)
  teacher.py   선생님 메뉴
```
