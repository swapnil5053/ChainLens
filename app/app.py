import os
import sys
import streamlit as st

# Ensure the app/ directory is in sys.path so 'core' imports work correctly
# regardless of where the streamlit run command was launched from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Defensive safeguard: Environment key validation
from dotenv import load_dotenv
load_dotenv()
if not os.getenv("GOOGLE_API_KEY"):
    st.error("Missing GOOGLE_API_KEY environment variable. Please specify it inside your .env file.")
    st.stop()

# Core imports
from core.ingestion import save_uploaded_file
from core.session_state import initialize_session_state_variables
from core.retriever import get_vectorstore
from core.rag_pipeline import chat

class ChatApp:
    """
    ChainLens - Supply Chain Document Analyzer.
    Uses Streamlit for a minimal, clean, native dark-theme UI.
    """
    def __init__(self):
        # Ensure target cache directory exists
        if not os.path.exists("docs"):
            os.makedirs("docs")

        # Initial Streamlit configurations
        st.set_page_config(
            page_title="ChainLens",
            page_icon="🔍",
            layout="wide"
        )
        
        # Inject modern minimal CSS overrides (neutral dark tones, system font stack)
        st.markdown("""
        <style>
            /* Base background & typography override */
            .stApp {
                background-color: #0f172a;
                color: #e2e8f0;
            }
            body, input, button, select, textarea, [class*="st-"] {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
            }
            
            /* Clean input bar */
            div[data-testid="stChatInput"] input {
                background-color: #1e293b !important;
                color: #f8fafc !important;
                border: 1px solid #334155 !important;
                border-radius: 8px !important;
            }
            
            /* Expander styles for context debugger */
            .streamlit-expanderHeader {
                background-color: #1e293b !important;
                border: 1px solid #334155 !important;
                border-radius: 6px !important;
                color: #cbd5e1 !important;
            }
            .streamlit-expanderContent {
                background-color: #0b0f19 !important;
                border-left: 1px solid #334155 !important;
                border-right: 1px solid #334155 !important;
                border-bottom: 1px solid #334155 !important;
                color: #94a3b8 !important;
                padding: 15px !important;
            }
            
            /* Metric labels in sidebar */
            div[data-testid="stMetricValue"] {
                color: #38bdf8 !important;
                font-size: 1.8rem !important;
            }
            
            /* Sidebar style improvements */
            section[data-testid="stSidebar"] {
                background-color: #0b0f19 !important;
                border-right: 1px solid #1e293b !important;
            }
            
            /* Chat message containers style overrides */
            div[data-testid="stChatMessage"] {
                border-radius: 8px !important;
                padding: 12px 16px !important;
                margin-bottom: 10px !important;
                border: 1px solid #1e293b !important;
            }
            div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageContent"]):nth-child(even) {
                background-color: #1e293b !important;
            }
            div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageContent"]):nth-child(odd) {
                background-color: #111827 !important;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # Initialize default state variables
        initialize_session_state_variables(st)
        self.docs_files = st.session_state.processed_documents

    def run(self):
        # Sidebar control column
        with st.sidebar:
            st.title("ChainLens")
            st.caption("Supply Chain Document Analyzer")
            st.markdown("---")
            
            upload_docs = os.listdir("docs")
            
            # Displays list of uploaded files in system cache
            st.subheader("Your Documents")
            if upload_docs:
                for doc in upload_docs:
                    st.markdown(f"• `{doc}`")
            else:
                st.info("No documents uploaded yet.")
            
            st.markdown("---")
            
            # Status Indicators
            if st.session_state.vectordb is None and upload_docs:
                st.info("⏳ Processing documents... Check progress.")
            elif st.session_state.vectordb is not None:
                st.success("✅ Document database loaded.")
            
            # Document uploader form
            st.subheader("Upload PDFs")
            pdf_docs = st.file_uploader(
                "Upload a PDF and click Process",
                type=['pdf'],
                accept_multiple_files=True
            )
            
            if pdf_docs:
                # Find new uploads
                new_files = [pdf for pdf in pdf_docs if pdf.name not in upload_docs]
                if new_files:
                    if st.button("Process Files", key="process_btn"):
                        for pdf in new_files:
                            save_uploaded_file(pdf)
                        
                        st.session_state.uploaded_pdfs.extend(pdf_docs)
                        
                        # Immediately trigger document parsing and embedding
                        try:
                            with st.spinner("Indexing documents..."):
                                st.session_state.vectordb = get_vectorstore(
                                    [pdf.name for pdf in new_files], 
                                    from_session_state=False
                                )
                            st.success("Indexing complete.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to process documents: {e}")
            
            st.markdown("---")
            
            # Metrics counter
            st.metric("Queries this session", st.session_state.get("query_count", 0))
            
            # Toggle for Retrieved Context Debug View
            show_context = st.toggle("Show Retrieved Context", value=False)
            
            st.markdown("<br><br><div style='text-align: center; color: #475569; font-size: 0.8rem;'>Built with Gemini & LangChain</div>", unsafe_allow_html=True)

        # Main Centered Content Column Layout (wide ratio [1, 2, 1])
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h2 style='text-align: center; margin-bottom: 0px;'>ChainLens</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #64748b; font-size: 0.95rem; margin-top: 5px; margin-bottom: 30px;'>Supply Chain Contract & SLA Auditing Dashboard</p>", unsafe_allow_html=True)
            
            # Chat flow unlocking
            if self.docs_files or st.session_state.uploaded_pdfs:
                # Dynamically load DB reference if file lengths mismatch
                try:
                    if len(upload_docs) > st.session_state.previous_upload_docs_length:
                        st.session_state.vectordb = get_vectorstore(upload_docs, from_session_state=True)
                        st.session_state.previous_upload_docs_length = len(upload_docs)
                    
                    # Double-check database reference
                    if st.session_state.vectordb is None and upload_docs:
                        with st.spinner("🔄 Loading document index..."):
                            st.session_state.vectordb = get_vectorstore(upload_docs, from_session_state=False)
                except Exception as e:
                    st.error(f"Failed to load document database: {e}")
                
                # Executing conversation loops
                if st.session_state.vectordb is not None:
                    st.session_state.chat_history = chat(
                        st.session_state.chat_history,
                        st.session_state.vectordb
                    )
                    
                    # Display context debug view if toggled on
                    if show_context and st.session_state.get("last_retrieved_context"):
                        st.markdown("<br>", unsafe_allow_html=True)
                        with st.expander("Retrieved Context (Debug View)", expanded=False):
                            for idx, doc in enumerate(st.session_state.last_retrieved_context):
                                src_name = os.path.basename(doc.metadata.get('source', 'Unknown'))
                                page_num = doc.metadata.get('page', 0) + 1
                                st.markdown(f"**Chunk {idx+1} — {src_name} (Page {page_num})**")
                                st.text_area(
                                    label=f"Content Chunk {idx+1}",
                                    value=doc.page_content,
                                    height=120,
                                    key=f"chunk_txt_{idx}",
                                    disabled=True
                                )
                                st.markdown("---")
                else:
                    st.info("⏳ Waiting for document indexing to complete. Upload files or check progress in the sidebar.")
            else:
                st.info("Upload a PDF document via the sidebar to start asking questions. Your uploaded files will remain persistent across sessions.")

if __name__ == "__main__":
    app = ChatApp()
    app.run()