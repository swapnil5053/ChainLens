import os
from core.retriever import get_vectorstore

def initialize_session_state_variables(st):
    """
    Initialize all session state variables defensively for the Streamlit application.
    """
    # Create docs folder if not exists
    if not os.path.exists("docs"):
        os.makedirs("docs")
        
    upload_docs = os.listdir("docs")
    
    # Defaults dictionary for session state variables
    defaults = {
        "chat_history": [],
        "uploaded_pdfs": [],
        "processed_documents": upload_docs,
        "vectordb": None,
        "query_count": 0,
        "previous_upload_docs_length": len(upload_docs),
        "last_retrieved_context": []
    }
    
    # Initialize basic defaults
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
            
    # Safely load the vector store if it hasn't been set yet
    if st.session_state.vectordb is None:
        try:
            if upload_docs and not os.path.exists("Vector_DB - Documents"):
                # Auto-process documents on first startup
                st.session_state.vectordb = get_vectorstore(upload_docs, from_session_state=False)
            else:
                st.session_state.vectordb = get_vectorstore(upload_docs, from_session_state=True)
        except Exception as e:
            # Prevent app startup failure due to corrupted/empty vector DB state
            st.warning(f"⚠️ Vector database startup check failed: {e}. If files are in 'docs', they will be processed upon next upload.")
            st.session_state.vectordb = None
