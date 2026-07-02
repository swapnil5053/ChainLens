import os
import sys

print("1. Set env vars", flush=True)

print("2. import streamlit", flush=True)
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("3. import ingestion", flush=True)
from core.ingestion import save_uploaded_file

print("4. import session_state", flush=True)
from core.session_state import initialize_session_state_variables

print("5. import retriever", flush=True)
from core.retriever import get_vectorstore

print("6. import rag_pipeline", flush=True)
from core.rag_pipeline import chat

print("ALL CLEAR", flush=True)
