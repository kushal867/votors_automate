import google.generativeai as genai
from groq import Groq
from django.conf import settings
import PyPDF2
import io
import json
import logging
import re
from duckduckgo_search import DDGS

# Setup Logging
logger = logging.getLogger(__name__)

def web_search(query):
    """
    Performs a web search using DuckDuckGo with a timeout/limit.
    """
    try:
        # Using a context manager for DDGS to ensure cleanup
        with DDGS(timeout=10) as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if not results:
                return "No real-time web results found for this query."
            
            search_context = "\n".join([f"Title: {r.get('title')}\nSnippet: {r.get('body')}\nSource: {r.get('href')}" for r in results])
            return search_context
    except Exception as e:
        logger.error(f"Search Error: {str(e)}")
        return f"Search service temporarily unavailable: {str(e)}"

def get_ai_response(prompt, system_instruction=None):
    """
    Core AI engine with Groq primary and Gemini fallback.
    """
    # 1. Groq is the Primary Engine (Extreme performance for Chatbot)
    if settings.GROQ_API_KEY:
        try:
            print(f"VVN-AI: Routing query through GROQ Intelligence Pipeline...")
            client = Groq(api_key=settings.GROQ_API_KEY)
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            chat_completion = client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.4, 
            )
            response = chat_completion.choices[0].message.content
            if response:
                return response
        except Exception as e:
            logger.warning(f"Groq API Error: {str(e)}. Falling back to Gemini...")
            print(f"DEBUG: Groq Failed, attempting Gemini fallback.")
    
    # Gemini Fallback Logic
    if not settings.GEMINI_API_KEY:
        return "AI Service Error: Groq failed and Gemini is not configured."
    
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # Use models from available_models.txt
        models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(
                    f"models/{model_name}",
                    system_instruction=system_instruction
                )
                response = model.generate_content(prompt)
                if response and response.text:
                    return response.text
            except Exception as e:
                logger.warning(f"Gemini {model_name} attempted and skipped: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Gemini Internal Error: {str(e)}")
            
    return "The AI high-council is currently disconnected. Please check your internet or API keys."

def extract_text_from_pdf(pdf_file, max_chars=40000):
    """
    Enhanced text extraction with better cleaning.
    """
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text_parts = []
        chars_count = 0
        
        for page in pdf_reader.pages:
            page_text = page.extract_text() or ""
            # Better cleaning: preserve some structure but remove excessive whitespace
            clean_page = re.sub(r'\s+', ' ', page_text).strip()
            text_parts.append(clean_page)
            chars_count += len(clean_page)
            
            if chars_count > max_chars:
                text_parts.append("\n[Document Truncated for Analysis Efficiency. Analysis based on first 40k characters.]")
                break
                
        return "\n".join(text_parts)
    except Exception as e:
        logger.error(f"PDF Extraction Error: {str(e)}")
        return f"Error reading PDF: {str(e)}"

def parse_structured_response(response_text):
    """
    Helps extract JSON from AI response if it's wrapped in markdown blocks.
    """
    try:
        # Try to find JSON block
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Try to find anything that looks like JSON
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
            
        return None
    except Exception:
        return None

def analyze_candidate_data(candidate):
    system_instruction = "You are an expert Political Analyst specializing in Nepali elections."
    prompt = f"""
    TASK: Provide a critical and neutral analysis of Candidate {candidate.name} from {candidate.party}.
    
    DATA PROVIDED:
    {candidate.past_work}
    
    REQUIREMENTS:
    1. Key Achievements (Bullet points)
    2. Policy Focus Areas
    3. Public Perception & Record
    4. Credibility Assessment (Based on provided data)
    
    Use a professional tone and professional Markdown formatting.
    """
    return get_ai_response(prompt, system_instruction)

def analyze_manifesto_vision(manifesto_text, candidate_name):
    system_instruction = "You are a Policy Researcher and Economic Analyst."
    prompt = f"""
    Analyze the Election Manifesto for {candidate_name}.
    
    TEXT:
    {manifesto_text[:15000]}
    
    EXTRACT & ANALYZE:
    1. CORE VISION: A high-level 2-sentence summary.
    2. PRIMARY PROMISES: List the top 5 most significant promises.
    3. ECONOMIC IMPACT: How does this affect the economy/budget?
    4. SWOT ANALYSIS: Strengths, Weaknesses, Opportunities, and Threats of this plan.
    
    IMPORTANT: You MUST also provide a JSON summary at the end of your response inside a ```json ``` block with these keys:
    {{
        "summary": "The 2-sentence vision",
        "promises": "Bullet points of key promises",
        "feasibility": "Score 1-10",
        "sentiment": "Neutral/Positive/Visionary"
    }}
    """
    return get_ai_response(prompt, system_instruction)

def analyze_multiple_manifestos(documents):
    if not documents:
        return "No documents provided for analysis."
        
    if len(documents) == 1:
        return analyze_manifesto_vision(documents[0]['text'], documents[0]['name'])
    
    system_instruction = "You are a Senior Political Intelligence Officer."
    prompt = f"""
    TASK: Comparative Intelligence Briefing on TWO Nepali Election Manifestos.
    
    DOC 1 ({documents[0]['name']}):
    {documents[0]['text'][:12000]}
    
    DOC 2 ({documents[1]['name']}):
    {documents[1]['text'][:12000]}
    
    COMPARISON CRITERIA:
    1. INFRASTRUCTURE & TECH: Compare digital and physical growth plans.
    2. SOCIAL WELFARE: Health, Education, and Poverty Alleviation.
    3. REALISM: Which plan is more grounded in fiscal reality?
    4. JANTAS VERDICT: What are the biggest pros and cons for the average citizen?
    
    Format with a comparative table using Markdown.
    """
    return get_ai_response(prompt, system_instruction)

def get_chatbot_response(user_query, context_data, history=None, web_results=None):
    """
    Main conversational engine with RAG (local data + web search).
    """
    system_msg = """
    ROLE: 'Voter Vision Nepal AI (VVN-AI)'. You are a highly sophisticated, neutral, and helpful election assistant.
    
    MANDATE:
    - Provide accurate, evidence-based information on Nepali politicians and elections.
    - If information is unverified or controversial, mention it as such.
    - Always maintain a polite and culturally aware tone (Namaste).
    - Use Markdown for readability.
    - Use source citations: [DB] for local database, [WEB] for web search.
    """
    
    history_context = ""
    if history:
        history_context = "\n".join([f"{'User' if m['role'] == 'user' else 'VVN-AI'}: {m['content']}" for m in history[-6:]])

    prompt = f"""
    INTELLECTUAL PRIORITY:
    1. PRIMARY SOURCE: Real-time Web Search Results (Highest priority for currency and breadth).
    2. SECONDARY SOURCE: Local Verified Database (Use ONLY for specific record validation).
    
    KNOWLEDGE CONTEXT:
    --- [WEB] REAL-TIME RESEARCH ---
    {web_results or 'No web results available for this query.'}
    
    --- [DB] LOCAL VERIFIED RECORDS ---
    {context_data or 'No local matching records found.'}
    
    --- CONVERSATION HISTORY ---
    {history_context or 'New conversation.'}
    
    USER QUERY: {user_query}
    
    INSTRUCTIONS:
    - Treat [WEB] results as your most current and vital intelligence source.
    - If [WEB] results are unavailable or show an error, you may use your internal training knowledge about Nepali politics and history to answer, but specify that this is from your general knowledge base and not a live search.
    - Mention [DB] data only if the user asks for specific records we have in our local database.
    - If there is a conflict between sources, prioritize the most recent or logical one.
    - Cite sources clearly as [WEB], [DB], or [AI-INTERNAL].
    - Always respond in a way that helps the voter, even if search results are thin.
    """
    
    return get_ai_response(prompt, system_msg)

