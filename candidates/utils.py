import google.generativeai as genai
from groq import Groq
from django.conf import settings
import PyPDF2
import io
from duckduckgo_search import DDGS

def web_search(query):
    """
    Performs a web search using DuckDuckGo and returns a summary of results.
    """
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=5)
            search_context = "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}\nSource: {r['href']}" for r in results])
            return search_context
    except Exception as e:
        print(f"Search Error: {e}")
        return "No web results found."

def get_ai_response(prompt):
    # Try Groq First (Extremely Fast and good limits)
    if settings.GROQ_API_KEY:
        try:
            client = Groq(api_key=settings.GROQ_API_KEY)
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama-3.3-70b-versatile",
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq Error: {str(e)}")
            # Fallback to Gemini if Groq fails
    
    # Gemini Fallback Logic
    if not settings.GEMINI_API_KEY:
        return "AI API Keys not configured. Please check .env file."
    
    genai.configure(api_key=settings.GEMINI_API_KEY)
    models_to_try = ['gemini-1.5-flash', 'gemini-pro']
    
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e) or "404" in str(e):
                continue
            return f"Error connecting to AI: {str(e)}"
            
    return "All AI models failed or reached quota. Please check your API keys."

def extract_text_from_pdf(pdf_file, max_chars=30000):
    """
    Extracts text with cleaning and size limiting for efficiency.
    """
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text_parts = []
        chars_count = 0
        
        for page in pdf_reader.pages:
            page_text = page.extract_text() or ""
            # Basic cleaning: remove excessive whitespace
            clean_page = " ".join(page_text.split())
            text_parts.append(clean_page)
            chars_count += len(clean_page)
            
            if chars_count > max_chars:
                text_parts.append("\n[Document Truncated for Analysis Efficiency...]")
                break
                
        return "\n".join(text_parts)
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def analyze_candidate_data(candidate):
    prompt = f"""
    Analyze the following past work and achievements of candidate {candidate.name} from {candidate.party} party:
    
    {candidate.past_work}
    
    Provide a concise summary of their strengths, weaknesses, and overall impact as a leader.
    Format the output with clear headings.
    """
    return get_ai_response(prompt)

def analyze_manifesto_vision(manifesto_text, candidate_name):
    prompt = f"""
    Analyze the following election manifesto (Vision Document) for candidate {candidate_name}:
    
    {manifesto_text[:12000]}
    
    1. SUMMARY: A 2-sentence core vision summary.
    2. TOP 5 PROMISES: Bullet points of specifically what they will do.
    3. PROS & CONS: Side-by-side analysis of benefits and risks.
    4. FEASIBILITY: Is this realistic for Nepal?
    
    Format the response as a valid JSON with keys: "summary", "promises", "full_analysis". 
    If you cannot return JSON, just return a clear structured markdown.
    """
    # Note: We try to get structured info. If AI fails to give JSON, 
    # we handle it or just use the text as is.
    response = get_ai_response(prompt)
    return response

def analyze_multiple_manifestos(documents):
    """
    documents: List of dicts {'name': name, 'text': text}
    """
    if not documents:
        return "No documents provided for analysis."
        
    if len(documents) == 1:
        doc = documents[0]
        return analyze_manifesto_vision(doc['text'], doc['name'])
    
    # Dual Comparison - Enhanced with specific criteria
    prompt = f"""
    ROLE: Senior Political & Economic Analyst.
    TASK: Comparative Intelligence Briefing on TWO Nepali Election Manifestos.
    
    DOC 1 ({documents[0]['name']}):
    {documents[0]['text'][:12000]}
    
    DOC 2 ({documents[1]['name']}):
    {documents[1]['text'][:12000]}
    
    ANALYSIS REQUIREMENTS:
    1. COMPARATIVE TABLE: Economic Policy, Social Welfare, Infrastructure, and Governance.
    2. FEASIBILITY SCORE: Rate each (1-10) based on Nepal's current budget constraints.
    3. CRITICAL ANALYSIS: Identify 'Lip Service' vs 'Actionable Plans'.
    4. NEPAL-CENTRIC IMPACT: How does each plan affect the common citizen (Janta)?
    5. THE VERDICT: Which document provides a more sustainable roadmap for Nepal? (Be bold but neutral).
    
    Format with professional Markdown, using color-like indicators (e.g., [STRENGTH], [RISK]) if possible via text.
    """
    return get_ai_response(prompt)



def get_chatbot_response(user_query, context_data, history=None):
    """
    General chatbot function with conversational memory.
    history: List of dicts [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}]
    """
    
    # Construct conversation context from history
    history_context = ""
    if history:
        # Only take last 4 rounds to keep it efficient and within token limits
        recent_history = history[-4:]
        history_context = "\n".join([f"{'User' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in recent_history])

    prompt = f"""
    ROLE: 'Voter Vision Nepal AI', a local, expert, and neutral informative assistant.
    MISSION: Help Nepali citizens understand candidates using Ghosada Patra (Manifestos) and records.
    
    CULTURAL CONTEXT (NEPAL):
    - Use polite greetings (Namaste).
    - Use terms: Ghosada Patra, Pratinidhi Sabha, Ward, etc.
    - Mix English/Nepali if natural.
    
    KNOWLEDGE BASE:
    - LOCAL DATA (Verified): 
    {context_data[:10000]}
    
    CONVERSATION HISTORY (FOR CONTINUITY):
    {history_context or 'Beginning of conversation.'}
    
    CURRENT USER QUERY: {user_query}
    
    INSTRUCTIONS:
    1. SYNTHESIZE: Use BOTH local database info and Web Search results to provide the most updated and comprehensive answer.
    2. REAL-TIME FOCUS: If web search results contain newer information than the local database (e.g. recent controversies or news), highlight those to the user.
    3. NEUTRALITY: Maintain a strictly objective, non-partisan tone.
    4. FORMATTING: Use professional Markdown (bolding, lists). Avoid long paragraphs.
    """
    return get_ai_response(prompt)
