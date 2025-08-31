# Lucidya MCP Prototype

A production-oriented multi-agent customer experience (CX) research and outreach platform featuring real-time Ollama streaming, MCP servers, FAISS vector search, and a deterministic agent orchestration pipeline.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Ollama installed and running
- 4GB+ RAM
- Unix-like OS (Linux/macOS)

### Setup

1. **Clone and enter directory:**
```bash
git clone <repo>
cd lucidya_mcp_prototype
```

2. **Create virtual environment:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Install and configure Ollama:**
```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve &

# Pull the required model
ollama pull qwen3:0.6b
```

5. **Start MCP servers:**
```bash
bash scripts/start_mcp_servers.sh
```

6. **Seed vector store:**
```bash
python scripts/seed_vectorstore.py
```

7. **Start FastAPI backend:**
```bash
bash scripts/run_api.sh
# API will be available at http://localhost:8000
```

8. **Start Streamlit UI (new terminal):**
```bash
bash scripts/run_ui.sh
# UI will be available at http://localhost:8501
```

## 📋 Architecture

### Agent Pipeline
```
Hunter → Enricher → Contactor → Scorer
  ↓        ↓          ↓          ↓
  └──────→ Writer → Compliance → Sequencer → Curator
             ↓          ↓            ↓          ↓
         [Stream]   [Policy]    [Email]    [Handoff]
```

### Key Components
- **Agents**: Modular, single-responsibility agents with `run(state) -> state` interface
- **MCP Servers**: Real Python servers for Search, Email, Calendar, and Store operations
- **Vector Store**: FAISS IndexFlatIP with sentence-transformers embeddings
- **Streaming**: Real-time NDJSON streaming from Ollama to UI via FastAPI
- **Compliance**: Regional policy enforcement (CAN-SPAM, PECR, CASL)

## 🔧 API Endpoints

### Health Check
```bash
curl -s http://localhost:8000/health | jq
```

### Run Pipeline (Streaming)
```bash
# All companies
curl -N -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{}'

# Specific companies
curl -N -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"company_ids": ["acme", "techcorp"]}'
```

### Writer Streaming Test
```bash
curl -N -X POST http://localhost:8000/writer/stream \
  -H "Content-Type: application/json" \
  -d '{"company_id": "acme"}'
```

### List Prospects
```bash
curl -s http://localhost:8000/prospects | jq
```

### Get Prospect Details
```bash
curl -s http://localhost:8000/prospects/acme | jq
```

### Get Handoff Packet
```bash
curl -s http://localhost:8000/handoff/acme | jq
```

### Reset System
```bash
curl -X POST http://localhost:8000/reset
```

## 📺 UI Features

### Pipeline Tab
- Run pipeline for all or specific companies
- Real-time token streaming display
- Live event log with agent activities

### Prospects Tab
- Overview of all prospects
- Status indicators and fit scores
- Quick metrics dashboard

### Details Tab
- Deep dive into specific prospects
- View generated summaries and email drafts
- Access email threads and calendar slots

### Dev Tools Tab
- Test Writer agent streaming
- API endpoint reference
- Debug utilities

## 🎥 Demo

Embed demo video directly in GitHub README. You can store it either at the repo root (`Lucidya_test.webm`) or under `assets/Lucidya_test.webm`. The player below includes both paths and will use whichever exists.

<video controls width="100%">
  <source src="assets/Lucidya_test.webm" type="video/webm" />
  <source src="Lucidya_test.webm" type="video/webm" />
  Your browser does not support the video tag.
  <a href="assets/Lucidya_test.webm">Download the demo video</a>
  <a href="Lucidya_test.webm">Alternate link</a>
  <!-- Optional MP4 for broader compatibility -->
  <!-- <source src="assets/Lucidya_test.mp4" type="video/mp4" /> -->
</video>

Tip: Use Git LFS for large media files (recommended for videos):

```bash
git lfs install
git lfs track "assets/*.webm" "*.webm"
git add .gitattributes assets/Lucidya_test.webm Lucidya_test.webm
git commit -m "Add demo video"
```

## 🧪 Testing

Run the test suite:
```bash
pytest tests/ -v
```

Key test coverage:
- `test_dedupe.py`: Email and domain deduplication
- `test_compliance.py`: Footer insertion, suppression, policy enforcement
- `test_pipeline.py`: Full pipeline with mocked Ollama streaming

## 📁 Data Files

### companies.json
Seed companies with:
- Basic info (name, domain, industry, size)
- Pain points array
- Notes for context

### suppression.json
Suppression list entries:
- Type: email, domain, or company
- Value to suppress
- Reason and optional expiry

### footer.txt
Company footer template with:
- Organization identity
- Physical address
- Unsubscribe link

## 🔍 Troubleshooting

### Ollama Connection Issues
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Verify model is available
ollama list | grep qwen3
```

### MCP Server Issues
```bash
# Check server ports
lsof -i:9001,9002,9003,9004

# Restart servers
pkill -f 'mcp/servers'
bash scripts/start_mcp_servers.sh
```

### Vector Store Issues
```bash
# Rebuild index
rm data/faiss.index
python scripts/seed_vectorstore.py
```

## 🚢 Production Considerations

This prototype demonstrates:
- **Architectural clarity**: Clean separation of concerns
- **Technical execution**: Real streaming, vector search, MCP integration
- **Scalability patterns**: Async operations, event-driven architecture
- **Compliance readiness**: Policy enforcement framework
- **Observability**: Comprehensive event logging

For production deployment, consider:
- Containerization (Docker/Kubernetes)
- Production message queue (RabbitMQ/Kafka)
- Persistent database (PostgreSQL)
- Monitoring/alerting (Prometheus/Grafana)
- Rate limiting and authentication
- Load balancing for MCP servers
