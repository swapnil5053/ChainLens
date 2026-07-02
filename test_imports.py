import os
import sys
sys.path.insert(0, os.path.abspath("app"))

print("Starting imports...")

try:
    import chromadb
    print("1. chromadb ok")
except Exception as e:
    print(f"Error 1: {e}")

try:
    from langchain_community.document_loaders import PyPDFLoader
    print("2. PyPDFLoader ok")
except Exception as e:
    print(f"Error 2: {e}")

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    print("3. RecursiveCharacterTextSplitter ok")
except Exception as e:
    print(f"Error 3: {e}")

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    print("4. GoogleGenerativeAIEmbeddings ok")
except Exception as e:
    print(f"Error 4: {e}")

try:
    from langchain_community.vectorstores import Chroma
    print("5. Chroma ok")
except Exception as e:
    print(f"Error 5: {e}")

try:
    from core.retriever import BatchGoogleGenerativeAIEmbeddings
    print("6. BatchGoogleGenerativeAIEmbeddings ok")
except Exception as e:
    print(f"Error 6: {e}")

print("All imports finished successfully!")
