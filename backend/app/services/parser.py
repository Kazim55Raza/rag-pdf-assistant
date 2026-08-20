import fitz  # PyMuPDF
from typing import List, Dict, Any

def parse_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parses PDF bytes and extracts text chunked by page.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if text:
            pages.append({
                "page_number": page_num + 1,
                "text": text
            })
            
    return pages