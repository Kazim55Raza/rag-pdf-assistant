import fitz  # PyMuPDF
import base64
import traceback
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from supabase import create_client
from groq import Groq

from app.core.config import settings
from app.services.embedder import generate_embeddings
from app.services.faiss_store import create_faiss_index

router = APIRouter()
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
groq_client = Groq(api_key=settings.GROQ_API_KEY)


def describe_image_with_groq(image_bytes: bytes) -> str:
    """Uses Groq Vision model to convert PDF images into searchable text descriptions."""
    try:
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        response = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe the contents of this image in detail, including any visible text, tables, diagrams, or key data points for indexing.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
            temperature=0.2,
            frequency_penalty=0.5,  # Prevents word repetition
            presence_penalty=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[VISION SKIPPED]: Could not analyze image: {str(e)}")
        return ""


def extract_chunks_from_pdf(pdf_bytes: bytes, document_id: str) -> list:
    """Streams through large PDFs page-by-page, extracts text, transcribes images, and chunks content."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chunks = []
    chunk_size = 750
    overlap = 200

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text").strip()

        # Extract and describe images on this page
        image_list = page.get_images(full=True)
        image_descriptions = []

        for img_index, img_info in enumerate(image_list[:3]):  # Limit to 3 major images per page
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]

            # Filter out minor UI elements and tiny icons (< 10KB)
            if len(img_bytes) > 10000:
                description = describe_image_with_groq(img_bytes)
                if description:
                    image_descriptions.append(f"[Image {img_index + 1} Context]: {description}")

        # Combine raw text with vision-generated descriptions
        full_page_content = page_text
        if image_descriptions:
            full_page_content += "\n\n" + "\n".join(image_descriptions)

        if not full_page_content.strip():
            continue

        # Create overlapping chunks for FAISS
        for i in range(0, len(full_page_content), chunk_size - overlap):
            chunk_text = full_page_content[i : i + chunk_size]
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "page_number": page_num + 1,
                    "document_id": document_id
                })

    doc.close()
    return chunks


@router.post("/process")
async def process_document(
    user_id: str = Form(...),
    document_id: str = Form(...),
    file: UploadFile = File(...)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are currently supported.")

    try:
        print(f"\n[PROCESSING]: Starting extraction for {file.filename} (ID: {document_id})")
        file_bytes = await file.read()

        # 1. High-speed page parsing and image extraction
        chunks = extract_chunks_from_pdf(file_bytes, document_id)

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Could not extract any readable text or image content from this PDF."
            )

        print(f"[PROCESSING]: Generated {len(chunks)} searchable chunks. Generating embeddings...")

        # 2. Generate local embeddings
        chunk_texts = [c["text"] for c in chunks]
        embeddings = generate_embeddings(chunk_texts)

        # 3. Build serialized FAISS index package
        faiss_package_bytes = create_faiss_index(chunks, embeddings)

        # 4. Upload .index file to Supabase Storage
        storage_path = f"{user_id}/{document_id}.index"
        supabase.storage.from_("user-documents").upload(
            file=faiss_package_bytes,
            path=storage_path,
            file_options={"content-type": "application/octet-stream", "upsert": "true"}
        )

        # 5. Update status in Supabase Database
        supabase.table("documents").update({"status": "ready"}).eq("id", document_id).execute()
        print(f"[PROCESSING SUCCESS]: {file.filename} indexed and ready!")

        return {"status": "success", "message": "Document processed and indexed successfully."}

    except Exception as e:
        print("\n================ PROCESS ERROR ================")
        traceback.print_exc()
        print("===============================================\n")
        supabase.table("documents").update({"status": "failed"}).eq("id", document_id).execute()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")