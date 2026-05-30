# 📈 AI Stock Report Generator

An agentic AI system that turns a plain-English request — *"Generate a report for Nvidia stock"* — into a professional, multi-section PDF report. Specialised agents research the company in parallel (market data, financials, news, SEC filings), generate embedded charts, write AI-authored narratives, and stream live progress to a Streamlit UI.

---

## 🎯 What It Does

```
User: "Generate a report for Nvidia stock"
  → Ticker resolved automatically via Gemini (NVDA)
  → Research Agent fetches price history, financials, news, SEC filings in parallel
  → Chart Builder generates price, revenue and margin charts (PNG)
  → Report Agent writes 10 sections via Gemini with embedded charts
  → PDF assembled with ReportLab and served for download
  → Every stage streamed live to the Streamlit UI via SSE
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Streamlit UI (port 8501)                      │
│  • Natural-language query input                                      │
│  • Live progress timeline (SSE events rendered in real time)         │
│  • Download button for the finished PDF                              │
└────────────────────────────┬─────────────────────────────────────────┘
                             │  GET /reports/stream?query=...
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (port 8000)                      │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    🧠 Orchestrator                             │  │
│  │  • Resolves ticker via Gemini                                  │  │
│  │  • Creates job in JobStore                                     │  │
│  │  • Drives Research → Report pipeline                          │  │
│  │  • Emits ProgressEvents into asyncio.Queue → SSE stream       │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                             │                                        │
│           ┌─────────────────┴──────────────────┐                    │
│           ▼                                    ▼                    │
│  ┌─────────────────────┐            ┌─────────────────────────┐     │
│  │  🔬 Research Agent  │            │  ✍️  Report Agent        │     │
│  │                     │            │                         │     │
│  │  Runs 4 tools in    │            │  Writes 10 sections via │     │
│  │  parallel:          │   ──────►  │  Gemini, builds charts, │     │
│  │  • Market data      │            │  assembles PDF          │     │
│  │  • Fundamentals     │            └─────────────────────────┘     │
│  │  • News (RSS)       │                                            │
│  │  • SEC filings      │                                            │
│  └─────────────────────┘                                            │
│                                                                      │
│  In-memory JobStore  │  GeminiClient  │  ChartBuilder  │ PDFGenerator│
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Request Flow

```
1. User submits query in Streamlit
        │
        ▼
2. GET /reports/stream — SSE connection opened
        │
        ▼
3. Orchestrator: resolve ticker with Gemini
        │  event: parse — "Identified: Nvidia (NVDA)"
        ▼
4. Research Agent: 4 asyncio tasks run concurrently
   ├── fetch_market_data   → 1-year prices + technical snapshot
   ├── fetch_fundamentals  → company info, 8 quarters financials, valuation
   ├── fetch_news          → Google News RSS headlines
   └── fetch_sec_filings   → EDGAR 10-K / 10-Q / 8-K filings
        │  event: research — per-tool progress
        ▼
5. Chart Builder: generates 3 PNG charts
   ├── Price chart  — 1Y close + MA50 + MA200
   ├── Revenue chart — quarterly Revenue + Net Income ($B)
   └── Margins chart — gross margin + operating margin (%)
        │
        ▼
6. Report Agent: 10 sections written by Gemini
   Each section prompt includes full research context
        │  event: report — per-section progress
        ▼
7. PDF Generator (ReportLab): assembles cover page → sections → sources → disclaimer
        │
        ▼
8. event: complete — artifact_url emitted → Streamlit shows download button
```

---

## 📄 Report Sections

| # | Section | Data Sources |
|---|---------|-------------|
| 1 | Executive Summary | All research context |
| 2 | Company Overview | yfinance company info |
| 3 | Price Performance | 1Y price history + MA50/MA200 chart |
| 4 | Financial Performance | Quarterly income statement + revenue chart |
| 5 | Margin Analysis | Gross & operating margins chart |
| 6 | Valuation | P/E, P/S, EV/EBITDA, forward metrics |
| 7 | News & Recent Catalysts | Google News RSS last 15 headlines |
| 8 | SEC Filings | EDGAR 10-K, 10-Q, 8-K recent filings |
| 9 | Risks & Red Flags | Synthesised from all data |
| 10 | Investment Thesis | Bull / bear case from Gemini |

---

## 📦 SSE Event Types

The `/reports/stream` endpoint emits Server-Sent Events throughout the pipeline:

| Event stage | When emitted | Payload fields |
|-------------|--------------|----------------|
| `job_start` | Connection established | `job_id` |
| `parse` | Ticker resolution | `stage`, `message` |
| `research` | Each data-fetch tool | `stage`, `message` |
| `report` | Each section written | `stage`, `message` |
| `complete` | PDF ready | `stage`, `message`, `done=true`, `artifact_url` |
| `error` | Pipeline failure | `stage`, `message`, `done=true` |

---

## 🚀 Setup

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) package manager
- Gemini API key from [Google AI Studio](https://aistudio.google.com/)

### Quick Start

```bash
# 1. Clone and enter the project
git clone <repo>
cd ai-stock-report

# 2. Create your .env file
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 3. Install dependencies
uv sync

# 4. Start the API server (terminal 1)
uv run ai-stock-report-api

# 5. Start the Streamlit UI (terminal 2)
uv run streamlit run streamlit_app.py

# 6. Open your browser
# Streamlit UI → http://localhost:8501
# API docs    → http://localhost:8000/docs
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI bind port |
| `REPORTS_DIR` | `reports/` | Directory where PDFs are saved |
| `NEWS_MAX_ITEMS` | `15` | Max news headlines to fetch |
| `PRICE_HISTORY_DAYS` | `365` | Days of price history for charts |
| `SEC_FILINGS_MAX` | `5` | Max SEC filings to include |

---

## 🔌 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/reports/stream` | GET | SSE stream — starts pipeline, emits all progress events |
| `/reports/{job_id}/status` | GET | Poll job status without streaming |
| `/reports/{job_id}/download` | GET | Download the generated PDF |

### Stream a report

```bash
curl -N "http://localhost:8000/reports/stream?query=Generate+a+report+for+Nvidia+stock"
```

### Download the PDF

```bash
curl -o nvidia_report.pdf "http://localhost:8000/reports/{job_id}/download"
```

---

## 📁 Project Structure

```
ai-stock-report/
├── app/
│   ├── agents/
│   │   ├── base.py              # BaseAgent abstract class + _event() helper
│   │   ├── research.py          # 🔬 Runs 4 data-fetch tools in parallel
│   │   └── report.py            # ✍️  Writes 10 sections via Gemini + assembles PDF
│   ├── models/
│   │   ├── stock.py             # Domain dataclasses: PriceBar, CompanyInfo, StockResearch, …
│   │   └── report.py            # ReportSection, ReportArtifact
│   ├── routers/
│   │   └── reports.py           # FastAPI routes: stream, status, download
│   ├── services/
│   │   ├── chart_builder.py     # 📊 Matplotlib price / revenue / margins charts → PNG
│   │   ├── gemini_client.py     # Thin async Gemini wrapper (generate / generate_json)
│   │   ├── job_store.py         # In-memory async job tracker (PENDING→RUNNING→DONE/FAILED)
│   │   └── pdf_generator.py     # 📄 ReportLab PDF assembly (cover, sections, disclaimer)
│   ├── tools/
│   │   ├── ticker_resolve.py    # LLM-based ticker extraction from natural language
│   │   ├── market_data.py       # yfinance price history + technical snapshot
│   │   ├── fundamentals.py      # yfinance company info, 8-quarter financials, valuation
│   │   ├── news.py              # Google News RSS feed (no API key needed)
│   │   └── sec_filings.py       # SEC EDGAR REST API — 10-K, 10-Q, 8-K
│   ├── config.py                # pydantic-settings (reads .env)
│   ├── dependencies.py          # FastAPI dependency injection providers
│   ├── orchestrator.py          # 🧠 Central pipeline controller + SSE queue
│   ├── schemas.py               # ReportRequest, ProgressEvent, ReportResponse
│   └── main.py                  # FastAPI app entry point + uvicorn runner
├── streamlit_app.py             # 🖥️  Streamlit UI with live progress timeline
├── .env.example                 # Environment variable template
├── pyproject.toml               # Project metadata + all dependencies
└── uv.lock                      # Locked dependency versions
```

---

## 🎨 Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| LLM | Gemini 2.5 Flash | Fast, capable, generous free tier |
| Streaming | FastAPI SSE (manual, no sse-starlette) | Zero extra dependency, full control |
| Market data | yfinance | Free, no API key, rich data |
| News | Google News RSS via feedparser | Free, no API key |
| SEC data | EDGAR REST API | Official, free, no API key |
| Charts | matplotlib Agg backend → PNG | Headless, embeds cleanly in PDF |
| PDF | ReportLab | Programmatic, precise layout |
| Job state | In-memory async JobStore | Simple MVP — no Redis needed |
| Package manager | uv | Fast, reproducible, `uv sync` just works |

---

## 💬 Example Queries

| Query | What happens |
|-------|-------------|
| `Generate a report for Nvidia stock` | Full pipeline — ticker resolved to NVDA |
| `Can you analyse Apple and make me a PDF?` | Ticker resolved to AAPL |
| `TSLA report` | Ticker used directly, no LLM resolution needed |
| `Microsoft stock analysis` | Resolved to MSFT |

---

## � Docker

### Local development

```bash
cp .env.example .env          # add your GEMINI_API_KEY
docker compose up --build     # starts api (8000) + streamlit (8501)
```

Streamlit → `http://localhost:8501`  |  API docs → `http://localhost:8000/docs`

### Individual services

```bash
# API only
docker build -t ai-stock-report-api -f Dockerfile .
docker run -p 8000:8000 --env-file .env ai-stock-report-api

# Streamlit only (point it at an existing API)
docker build -t ai-stock-report-streamlit -f Dockerfile.streamlit .
docker run -p 8501:8501 -e API_BASE=http://localhost:8000 ai-stock-report-streamlit
```

---

## ☁️ AWS Deployment

### Recommended Architecture

```
                 ┌─────────────────────────────────────────────────────┐
                 │                   AWS VPC                           │
                 │                                                     │
  Internet ────► │  Public ALB (:80/:443)                              │
                 │       │                                             │
                 │       ▼                                             │
                 │  ┌──────────────────────────────┐  Private subnet  │
                 │  │  ECS Fargate — Streamlit      │  (no public IP)  │
                 │  │  0.5 vCPU / 1 GB RAM          │                  │
                 │  └──────────────┬───────────────┘                  │
                 │                 │ http://internal-alb:8000          │
                 │  ┌──────────────▼───────────────┐                  │
                 │  │  ECS Fargate — API            │  Private subnet  │
                 │  │  0.5 vCPU / 1 GB RAM          │                  │
                 │  └──────────────┬───────────────┘                  │
                 │                 │                                   │
                 │  ┌──────────────▼───────────────┐                  │
                 │  │  Amazon EFS — reports/        │                  │
                 │  │  (shared PDF storage)         │                  │
                 │  └──────────────────────────────┘                  │
                 └─────────────────────────────────────────────────────┘
                        │                       │
              Secrets Manager            CloudWatch Logs
              (GEMINI_API_KEY)       (/ecs/ai-stock-report-*)
```

### AWS Services Used

| Service | Purpose | Why |
|---------|---------|-----|
| **ECR** | Container registry | Store API + Streamlit Docker images |
| **ECS Fargate** | Serverless container runtime | No EC2 to manage; pay per task |
| **ALB** (×2) | Load balancers | Public (Streamlit) + Internal (API) |
| **EFS** | Shared filesystem | PDF reports accessible to API containers |
| **Secrets Manager** | Secret storage | `GEMINI_API_KEY` never in env vars/images |
| **CloudWatch Logs** | Log aggregation | Container stdout/stderr |
| **VPC** | Network isolation | Private subnets, no public IPs on tasks |
| **ACM** | TLS certificate | HTTPS on the public ALB |
| **IAM** | Least-privilege roles | Task role + execution role |

### Step-by-Step Setup

#### 1. Prerequisites
```bash
aws --version          # AWS CLI v2
docker --version       # Docker 24+
# Ensure your IAM user has ECR, ECS, EFS, ALB, Secrets Manager permissions
```

#### 2. Create ECR repositories
```bash
aws ecr create-repository --repository-name ai-stock-report-api    --region us-east-1
aws ecr create-repository --repository-name ai-stock-report-streamlit --region us-east-1
```

#### 3. Store the Gemini API key
```bash
aws secretsmanager create-secret \
  --name ai-stock-report/GEMINI_API_KEY \
  --secret-string '{"GEMINI_API_KEY":"your_key_here"}' \
  --region us-east-1
```

#### 4. Create an EFS filesystem for reports
```bash
EFS_ID=$(aws efs create-file-system \
  --encrypted \
  --tags Key=Name,Value=ai-stock-report-reports \
  --query FileSystemId --output text)
echo "EFS ID: $EFS_ID"
# Create a mount target in each private subnet (repeat for each subnet)
aws efs create-mount-target --file-system-id $EFS_ID --subnet-id <SUBNET_ID>
```

#### 5. Create IAM roles
Create `ecsTaskExecutionRole` (allows ECR pull + CloudWatch Logs) and `ecsTaskRole` (allows Secrets Manager read + EFS access). Attach the managed policy `AmazonECSTaskExecutionRolePolicy` to the execution role.

#### 6. Create ECS cluster
```bash
aws ecs create-cluster --cluster-name ai-stock-report --region us-east-1
```

#### 7. Update and register task definitions
Edit `infra/ecs-task-api.json` and `infra/ecs-task-streamlit.json` — replace all `<PLACEHOLDER>` values:

| Placeholder | Value |
|-------------|-------|
| `<ACCOUNT_ID>` | Your 12-digit AWS account ID |
| `<REGION>` | e.g. `us-east-1` |
| `<EFS_FILE_SYSTEM_ID>` | The EFS ID from step 4 |
| `<INTERNAL_ALB_DNS>` | DNS name of the internal ALB (step 8) |

```bash
aws ecs register-task-definition --cli-input-json file://infra/ecs-task-api.json
aws ecs register-task-definition --cli-input-json file://infra/ecs-task-streamlit.json
```

#### 8. Create ALBs and ECS services
Use the AWS Console or CloudFormation to:
1. Create an **internal** ALB (port 8000) → target group → API ECS service
2. Create a **public** ALB (port 80/443) → target group → Streamlit ECS service
3. Create both ECS services with `--launch-type FARGATE`, assigned to private subnets, with the matching target group

#### 9. First deploy
```bash
chmod +x infra/deploy.sh

# Set your values
export AWS_REGION=us-east-1
export ECS_CLUSTER=ai-stock-report

./infra/deploy.sh
```

### CI/CD with GitHub Actions

The workflow at `.github/workflows/deploy.yml` runs on every push to `main`.

**Required GitHub secrets:**

| Secret | Value |
|--------|-------|
| `AWS_ROLE_ARN` | ARN of the IAM role to assume (OIDC) |

Or if using static keys instead:

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | IAM access key |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key |

> **OIDC is strongly recommended** — no long-lived credentials stored in GitHub.
> Follow the [AWS OIDC guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) to set up the trust relationship.

### Estimated Monthly Cost (us-east-1)

| Resource | Config | Est. cost |
|----------|--------|-----------|
| ECS Fargate — API | 0.5 vCPU / 1 GB, 730 h | ~$15 |
| ECS Fargate — Streamlit | 0.5 vCPU / 1 GB, 730 h | ~$15 |
| ALB (×2) | ~10 LCU each | ~$18 |
| EFS | 1 GB storage | < $1 |
| ECR | 2 repos, ~500 MB | ~$0.05 |
| Secrets Manager | 1 secret | < $1 |
| CloudWatch Logs | moderate volume | ~$2 |
| **Total** | | **~$51 / month** |

> Scale down to on-demand or use Fargate Spot tasks to cut compute costs by up to 70 %.

---

## 🔒 Notes

- All data sources are **free and require no API keys** except Gemini.
- The `reports/` directory is created automatically on first run (local) or mounted from EFS (AWS).
- Job state is **in-memory only** — restarting the API server clears all jobs. Add Redis/DynamoDB for persistence.
- The Streamlit UI connects synchronously via `httpx` streaming — keep both processes running.
- `API_BASE` defaults to `http://localhost:8000`; set it via env var for Docker or ECS.
