import os
import threading
from collections import defaultdict
import streamlit as st
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from core.retriever import get_retriever

def get_context_retriever_chain(vectordb):
    """
    Create a context retriever chain using LCEL.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=env_path)
    load_dotenv()
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment. Please add it to your .env file.")
    
    # Initialize the LLM (Gemini 2.5 Flash is recommended, faster and supports system instructions well)
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        temperature=0.2, 
        convert_system_message_to_human=True, 
        google_api_key=api_key
    )
    
    # Get the MMR retriever
    retriever = get_retriever(vectordb)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are ChainLens, a semantic document assistant built for Supply Chain Managers. Your task is to respond to the user's query utilizing the provided context documents. Rely strictly on the context and avoid external knowledge. If the documents do not contain the answer, state that the context is insufficient. Do not formulate answers outside the context. Context: {context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # LCEL pipeline returning dictionary containing prompt, formatted context documents, and string answers
    retrieval_chain = (
        RunnablePassthrough.assign(
            context=lambda x: retriever.invoke(x["input"]),
            _docs=lambda x: retriever.invoke(x["input"])
        )
        | RunnablePassthrough.assign(
            answer=(
                RunnablePassthrough.assign(
                    context=lambda x: format_docs(x["context"])
                )
                | prompt
                | llm
                | StrOutputParser()
            )
        )
    )
    return retrieval_chain

def get_response(question, chat_history, vectordb):
    """
    Generate a response to the user's question with timeout checking and error handling.
    """
    try:
        chain = get_context_retriever_chain(vectordb)
        result_container = {"response": None, "error": None}
        
        def invoke_with_timeout():
            try:
                result_container["response"] = chain.invoke({"input": question, "chat_history": chat_history})
            except Exception as e:
                result_container["error"] = e
        
        # Invoke LLM chain in background thread to prevent GUI lockups on slow connections
        thread = threading.Thread(target=invoke_with_timeout)
        thread.daemon = True
        thread.start()
        thread.join(timeout=30.0)
        
        if thread.is_alive():
            raise TimeoutError("LLM response generation timed out after 30 seconds.")
        
        if result_container["error"]:
            raise result_container["error"]
        
        if result_container["response"]:
            res_dict = result_container["response"]
            answer = res_dict.get("answer", "")
            retrieved_docs = res_dict.get("context", [])
            
            # Format sources metadata dictionary
            sources_dict = defaultdict(list)
            for doc in retrieved_docs:
                src = doc.metadata.get('source', 'Unknown')
                page = doc.metadata.get('page', 0)
                sources_dict[src].append(page)
            
            formatted_sources = {src: sorted(list(set(pgs))) for src, pgs in sources_dict.items()}
            
            return {
                "answer": answer,
                "sources": formatted_sources,
                "context": retrieved_docs
            }
        else:
            raise ValueError("Empty response received from LLM chain.")
            
    except Exception as e:
        # Graceful return containing error details
        import sys
        print(f"Error in RAG Pipeline: {e}", file=sys.stderr)
        return {
            "answer": "An internal error occurred while generating the response.",
            "sources": {},
            "context": [],
            "error": str(e)
        }

def chat(chat_history, vectordb):
    """
    Render chatbot interaction stream and update history states.
    """
    user_query = st.chat_input("Ask a question:")
    if user_query is not None and user_query != "":
        # Prevent empty queries
        if not user_query.strip():
            st.warning("Please enter a question.")
            st.stop()
            
        # Check that we actually have elements indexed before calling RAG
        # This is a defensive check to prevent crashing on empty database
        if vectordb is not None:
            try:
                # Access Chroma's collection client defensively
                count = vectordb._collection.count()
                if count == 0:
                    st.info("No indexed documents found. Please upload and process PDFs first.")
                    st.stop()
            except Exception:
                pass
        
        # Add human query message to memory
        chat_history = chat_history + [HumanMessage(content=user_query)]
        
        # Increment queries counter metrics
        st.session_state.query_count = st.session_state.get("query_count", 0) + 1
        
        try:
            with st.spinner("🤔 Thinking... (max 30 seconds)"):
                response_data = get_response(user_query, chat_history[:-1], vectordb)
            
            # Extract attributes from structured RAG return format
            response_text = response_data.get("answer", "")
            retrieved_docs = response_data.get("context", [])
            sources = response_data.get("sources", {})
            error = response_data.get("error", None)
            
            # Format query error if returned
            if error:
                response_text = f"**Error:** {response_text}\n\n*Details: {error}*"
                
            # Add assistant message to memory
            chat_history = chat_history + [AIMessage(content=response_text)]
            
            # Display source citations on the sidebar
            if sources:
                with st.sidebar:
                    st.subheader("📚 Sources")
                    for source, pages in sources.items():
                        st.write(f"**{os.path.basename(source)}**")
                        st.write(f"Pages: {', '.join(map(str, pages))}")
                        
            # Store last retrieved context documents in session state for the "Debug View" layout
            st.session_state.last_retrieved_context = retrieved_docs
            
        except Exception as e:
            error_response = f"**Error generating response:** {str(e)}"
            chat_history = chat_history + [AIMessage(content=error_response)]
            st.session_state.last_retrieved_context = []
            
    # Render historical transcripts
    for message in chat_history:
        with st.chat_message("AI" if isinstance(message, AIMessage) else "Human"):
            if isinstance(message, AIMessage) and "**Error:**" in message.content:
                st.error(message.content)
            else:
                st.write(message.content)
                
    return chat_history
