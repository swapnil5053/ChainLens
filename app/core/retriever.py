import os
import logging
import warnings
import chromadb
from typing import List
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
import google.generativeai as genai

# Import parsing utility from ingestion module
from core.ingestion import extract_pdf_text, get_text_chunks

# Suppress ChromaDB tenant warnings (harmless when using local PersistentClient)
chromadb_logger = logging.getLogger("chromadb")
chromadb_logger.setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="chromadb")

class BatchGoogleGenerativeAIEmbeddings:
    """
    Custom embedding class that uses batch embedding to reduce API calls.
    Processes up to 100 chunks per API call instead of 1 chunk per call.
    """
    def __init__(self, model="models/gemini-embedding-001", google_api_key=None):
        # Load API key
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_path = os.path.join(project_root, '.env')
        load_dotenv(dotenv_path=env_path)
        load_dotenv()
        
        self.api_key = google_api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment. Please add it to your .env file.")
        
        self.model = model
        genai.configure(api_key=self.api_key)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts using batch processing to stay within quota limits.
        """
        if not texts:
            return []
        
        embeddings = []
        batch_size = 100
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                # Use Gemini's native batch embedding
                result = genai.embed_content(
                    model=self.model,
                    content=batch,
                    task_type="retrieval_document"
                )
                
                # Extract embeddings from batch result
                if isinstance(result, dict) and 'embedding' in result:
                    batch_embeddings = result['embedding']
                    if len(batch_embeddings) == len(batch):
                        embeddings.extend(batch_embeddings)
                    else:
                        raise ValueError(f"Expected {len(batch)} embeddings, got {len(batch_embeddings)}")
                else:
                    raise ValueError(f"Unexpected result format: {type(result)}")
                    
            except Exception as e:
                # Fallback to individual calls
                print(f"Batch embedding failed, falling back to individual calls: {e}")
                for text in batch:
                    try:
                        result = genai.embed_content(
                            model=self.model,
                            content=text,
                            task_type="retrieval_document"
                        )
                        if isinstance(result, dict) and 'embedding' in result:
                            embeddings.append(result['embedding'])
                        else:
                            raise ValueError(f"Unexpected individual embedding result format: {type(result)}")
                    except Exception as individual_error:
                        raise RuntimeError(f"Failed to generate embedding for text: {individual_error}") from individual_error
        
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query text.
        """
        try:
            result = genai.embed_content(
                model=self.model,
                content=text,
                task_type="retrieval_query"
            )
            if isinstance(result, dict) and 'embedding' in result:
                return result['embedding']
            else:
                raise ValueError(f"Unexpected result format: {type(result)}")
        except Exception as e:
            raise Exception(f"Error embedding query: {e}")

def get_vectorstore(pdfs, from_session_state=False):
    """
    Create or retrieve a vectorstore from PDF documents with error handling.
    """
    # Load .env configurations
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=env_path)
    load_dotenv()
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment. Please add it to your .env file.")
    
    # Initialize the custom batch embedding client
    embedding = BatchGoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=api_key
    )
    
    db_path = "Vector_DB - Documents"
    
    # Attempt to load vectorstore from directory if requested
    if from_session_state and os.path.exists(db_path):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                client = chromadb.PersistentClient(path=db_path)
            
            vectordb = Chroma(client=client, embedding_function=embedding)
            
            # Cross-reference existing files in database to check if any PDF is missing
            try:
                existing_collection = client.get_collection(name="langchain")
                existing_docs = set()
                if existing_collection.count() > 0:
                    items = existing_collection.get(limit=10000)
                    if items and 'metadatas' in items:
                        for metadata in items['metadatas']:
                            source = metadata.get('source', '')
                            if source.startswith('docs\\') or source.startswith('docs/'):
                                existing_docs.add(os.path.basename(source))
                
                missing_docs = [pdf for pdf in pdfs if pdf not in existing_docs]
                if missing_docs:
                    import streamlit as st
                    with st.sidebar:
                        st.warning(f"⚠️ Found {len(missing_docs)} new document(s) not in database. Reprocessing...")
                    return None
                else:
                    return vectordb
            except Exception:
                # If checking fails, return existing vector DB reference gracefully
                return vectordb
        except Exception as e:
            raise RuntimeError(f"Failed to initialize vector database: {e}")
            
    elif not from_session_state:
        import streamlit as st
        # Render a structured sidebar progress indicators
        with st.sidebar:
            st.subheader("📊 Processing Status")
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        try:
            status_text.text("📄 Step 1/4: Extracting text from PDF...")
            progress_bar.progress(10)
            docs = extract_pdf_text(pdfs)
            
            status_text.text(f"✂️ Step 2/4: Chunking text into {len(docs)} pages...")
            progress_bar.progress(30)
            chunks = get_text_chunks(docs)
            
            status_text.text(f"🔢 Step 3/4: Generating embeddings for {len(chunks)} chunks...")
            progress_bar.progress(50)
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                client = chromadb.PersistentClient(path=db_path)
                
            try:
                vectordb = Chroma.from_documents(documents=chunks, embedding=embedding, client=client)
            except Exception as db_err:
                raise RuntimeError(f"Failed to save documents to vector database: {db_err}")
            
            status_text.text("💾 Step 4/4: Saving to database...")
            progress_bar.progress(90)
            
            status_text.text(f"✅ Complete! Processed {len(chunks)} chunks")
            progress_bar.progress(100)
            
            st.success(f"✅ **Successfully processed {len(pdfs)} document(s)!** You can now start chatting below.")
            return vectordb
            
        except Exception as e:
            progress_bar.progress(0)
            if "quota" in str(e).lower() or "429" in str(e):
                status_text.text("❌ Quota Exceeded")
                st.error("""
                **🚫 Quota Limit Reached** 
                
                Your free tier API quota has been exceeded. Please:
                1. **Wait 24 hours** for quota reset, then restart the app.
                2. **Upgrade to paid tier** at https://ai.google.dev/pricing.
                """)
            else:
                status_text.text(f"❌ Error: {str(e)[:100]}")
                st.error(f"**Error processing documents:** {str(e)}")
            raise
            
    return None

def get_retriever(vectordb):
    """
    Helper to construct and return an MMR retriever for context diversity.
    
    Parameters:
    - vectordb: Vectorstore client.
    
    Returns:
    - Retriever: Configured MMR retrieval client.
    """
    return vectordb.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 6, "lambda_mult": 0.5}
    )
