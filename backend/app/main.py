from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import process, chat

app = FastAPI(title="Free Multi-Tenant RAG Engine")

# Enable CORS for Next.js Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(process.router, prefix="/api", tags=["Document Processing"])
app.include_router(chat.router, prefix="/api", tags=["RAG Chat"])

@app.get("/")
def root():
    return {"status": "ok", "message": "RAG Engine Active"}