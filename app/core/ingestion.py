import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def extract_pdf_text(pdfs):
    """
    Extract text from PDF documents cached in the local docs directory.
    
    Parameters:
    - pdfs (list): List of PDF file names.
    
    Returns:
    - list: Loaded document pages with content and metadata.
    """
    docs = []
    for pdf in pdfs:
        pdf_path = os.path.join("docs", pdf)
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        # Load text from the PDF and extend the list of documents
        docs.extend(PyPDFLoader(pdf_path).load())
    return docs

def get_text_chunks(docs):
    """
    Split loaded document pages into clean text chunks.
    
    Parameters:
    - docs (list): List of text documents.
    
    Returns:
    - list: Chunky text segments ready for embedding.
    """
    # Chunk size is configured to be an approximation to the model limit of 2048 tokens
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=8000, 
        chunk_overlap=800, 
        separators=["\n\n", "\n", " ", ""]
    )
    return text_splitter.split_documents(docs)

def save_uploaded_file(uploaded_file):
    """
    Saves an uploaded Streamlit file to the local cache directory.
    
    Parameters:
    - uploaded_file: Streamlit UploadedFile object.
    
    Returns:
    - str: Saved file path.
    """
    if not os.path.exists("docs"):
        os.makedirs("docs")
    file_path = os.path.join("docs", uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    return file_path
