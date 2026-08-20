import json
import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from groq import Groq
from supabase import create_client
from app.core.config import settings
from app.services.embedder import generate_embeddings
from app.services.faiss_store import search_faiss_index
from app.services.repetition_guard import deduplicate_chunks, collapse_repeated_phrases

router = APIRouter()
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
groq_client = Groq(api_key=settings.GROQ_API_KEY)

class ChatRequest(BaseModel):
    user_id: str
    document_id: str
    query: str

@router.post("/chat")
async def chat_with_document(request: ChatRequest):
    try:
        # 1. Fetch user FAISS index from Supabase Storage
        storage_path = f"{request.user_id}/{request.document_id}.index"
        
        index_bytes = supabase.storage.from_("user-documents").download(storage_path)
        if not index_bytes:
            raise HTTPException(status_code=404, detail="Vector index file not found.")

        # 2. Embed user query locally
        query_embedding = generate_embeddings([request.query])

        # 3. Retrieve top matching chunks via FAISS
        retrieved_chunks = search_faiss_index(index_bytes, query_embedding, top_k=4)

        # --- DEDUPLICATION STEP ---
        relevant_chunks = deduplicate_chunks(retrieved_chunks)
        # ---------------------------

        if not relevant_chunks:
            async def empty_stream():
                yield f"data: {json.dumps({'type': 'token', 'data': 'I could not find relevant information in this document to answer your query.'})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(empty_stream(), media_type="text/event-stream")

        # 4. Construct context window & system prompt
        context_str = "\n\n".join([
            f"[Page {c['page_number']}]: {c['text']}" for c in relevant_chunks
        ])

        system_prompt = (
            "You are an intelligent document assistant. Answer the user's question accurately using ONLY "
            "the provided context snippets below.\n\n"
            "STRICT RESPONSE RULES:\n"
            "1. Use only facts present in the document context. Do not invent or assume missing information.\n"
            "2. Do not repeat the same sentence, phrase, or idea more than once.\n"
            "3. When the same fact appears multiple times in the source, state it once in a clean, concise answer.\n"
            "4. Put a double line break before and after every section heading.\n"
            "5. Every header MUST start on a brand new line with '### '.\n"
            "6. Every list item MUST start on a brand new line with a bullet point ('* ' or '- ').\n"
            "7. Do not include page citations or bracket tags in the body text; sources are shown separately.\n"
            "8. Keep the answer direct and non-redundant.\n\n"
            f"--- DOCUMENT CONTEXT ---\n{context_str}"
        )

        # 5. Define token streaming generator
        async def generate_stream():
            # Send source metadata first (deduplicated by page_number if desired)
            sources = [
                {"page_number": c["page_number"], "snippet": c["text"][:150] + "..."}
                for c in relevant_chunks
            ]
            yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"

            # Stream response word-by-word from Groq
            response_stream = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                # model ="qwen/qwen3.6-27b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.query}
                ],
                temperature=0.6,          # Raised to prevent token locking
                frequency_penalty=0.8,    # Strongly penalizes repeating phrases
                presence_penalty=0.5,     # Encourages new topic introduction
                stream=True
            )

            assembled_text = ""
            for chunk in response_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    assembled_text += token
                    yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"

            final_text = collapse_repeated_phrases(assembled_text)
            if final_text != assembled_text:
                yield f"data: {json.dumps({'type': 'token', 'data': ' '})}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(generate_stream(), media_type="text/event-stream")

    except Exception as e:
        print("\n================ DETAILED BACKEND ERROR ================")
        traceback.print_exc()
        print("========================================================\n")
        raise HTTPException(status_code=500, detail=f"Chat execution failed: {str(e)}")