# 📄 AI Document Chatbot (RAG System)

A full-stack Retrieval-Augmented Generation (RAG) platform that enables users to upload PDF documents, index vector embeddings, and stream real-time context-aware answers using Groq LLMs.

---

## 🌟 Key Features

* **PDF Ingestion & Processing**: Extracts raw document text locally using PyMuPDF (`fitz`).
* **Vector Indexing**: Generates local vector embeddings using Sentence-Transformers and stores index files (`.index`) via FAISS and Supabase Storage.
* **Context-Aware RAG Pipeline**: Performs fast similarity searching to retrieve relevant document chunks while avoiding near-duplicate context loops.
* **Token Streaming (SSE)**: Streams answers word-by-word into the client via Server-Sent Events.
* **Source Citations**: Displays deduplicated page badges showing exact document references for each answer.
* **Authentication**: Passwordless email magic-link authentication powered by Supabase.

---

## 🛠️ Tech Stack

### Frontend
* **Framework**: Next.js (TypeScript) / React 18
* **Styling**: Tailwind CSS
* **Utilities**: Axios, ReactMarkdown, Supabase JS SDK

### Backend
* **Framework**: FastAPI (Python)
* **LLM Orchestration**: Groq API (`llama-3.3-70b-versatile` / `gpt-oss-120b`)
* **Embeddings & Vector Search**: HuggingFace Sentence-Transformers + FAISS
* **PDF Parsing**: PyMuPDF (`fitz`)

### Database & Storage
* **PostgreSQL**: Supabase Database (document metadata)
* **Object Storage**: Supabase Storage (`user-documents` bucket)

---

## 🚀 Getting Started

### Prerequisites
* **Python**: 3.10 or higher
* **Node.js**: v18 or higher
* **Supabase Account**: Project URL, Service Role Key, and Anon Key
* **Groq API Key**: Active key from Groq Console

---

### 1. Backend Setup


# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install required dependencies
pip install fastapi uvicorn PyMuPDF faiss-cpu sentence-transformers groq supabase python-dotenv

# Create a .env file inside /backend
cat <<EOT> .env
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
GROQ_API_KEY=your_groq_api_key
EOT

# Start the FastAPI server
uvicorn app.main:app --reload
---

### 2. Frontend Setup

# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Create a .env.local file inside /frontend
cat <<EOT> .env.local
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_FASTAPI_URL=http://localhost:8000
EOT

# Start the development server
npm run dev


# Project Architecture

├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── chat.py       # RAG context lookup & SSE streaming endpoint
│   │   │       └── process.py    # PDF parsing & FAISS indexing endpoint
│   │   ├── core/                 # Config & environment settings
│   │   └── services/             # Embedder and FAISS management
│   └── main.py
│
└── frontend/
    ├── app/
    │   └── page.tsx              # Main Dashboard UI & streaming state handler
    └── lib/
        └── supabase.ts           # Supabase client configuration