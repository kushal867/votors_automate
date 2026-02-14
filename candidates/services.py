from .utils import web_search, get_chatbot_response, parse_structured_response
import logging
import re

logger = logging.getLogger(__name__)

def get_relevant_context(user_query):
    """
    Main Intelligence Service: Prioritizes Web Research for real-time accuracy.
    Local database info is used as secondary validation only.
    """
    query_lower = user_query.lower()
    
    # 1. Intelligence Refinement: Handle nicknames and broader context
    # This specifically addresses the 'Kpoli' vs 'KP Sharma Oli' search quality issue.
    search_query = user_query
    
    # Nickname Resolution Map for Nepali Politics
    nicknames = {
        'kpoli': 'KP Sharma Oli',
        'kp oli': 'KP Sharma Oli',
        'prachanda': 'Pushpa Kamal Dahal',
        'deuba': 'Sher Bahadur Deuba',
        'rabi': 'Rabi Lamichhane',
        'balen': 'Balendra Shah',
        'gyane': 'Gyanendra Shahi'
    }
    
    refined_query = user_query
    for nick, full in nicknames.items():
        if nick in query_lower:
            refined_query = refined_query.replace(nick, full)
    
    # Ensure Nepal context is always present for better results
    if 'nepal' not in refined_query.lower():
        search_query = f"{refined_query} Nepal politics"
    else:
        search_query = refined_query
            
    try:
        web_results = web_search(search_query)
        logger.info(f"Refined search query: {search_query}")
    except Exception as e:
        logger.error(f"Failed to gather web intelligence: {e}")
        web_results = "Operational constraint: Web search currently throttled."

    # 2. Gather localized records only if specifically relevant to avoid bias/limitations
    candidates = Candidate.objects.all()
    relevant_candidates = []
    
    for c in candidates:
        # Use regex with word boundaries to avoid partial matches (e.g. 'Ali' in 'Validity')
        if re.search(r'\b' + re.escape(c.name.lower()) + r'\b', query_lower):
            relevant_candidates.append(c)

    context_parts = []
    for c in relevant_candidates:
        c_info = f"[LOCAL RECORD] Candidate: {c.name}\n"
        if c.ai_work_analysis:
            c_info += f"Analysis: {c.ai_work_analysis[:500]} \n"
        context_parts.append(c_info)
    
    local_context = "\n---\n".join(context_parts)
    
    return local_context, web_results

def process_manifesto_upload(manifesto_obj, raw_analysis, text_content):
    """
    Service to process the AI analysis of a manifesto and populate fields.
    """
    structured_data = parse_structured_response(raw_analysis)
    
    if structured_data:
        manifesto_obj.vision_summary = structured_data.get('summary', text_content[:500])
        manifesto_obj.key_promises = structured_data.get('promises', '')
        # Store full analysis as well
        manifesto_obj.ai_vision_analysis = raw_analysis
    else:
        # Fallback if AI didn't provide JSON
        manifesto_obj.vision_summary = text_content[:500]
        manifesto_obj.ai_vision_analysis = raw_analysis
    
    manifesto_obj.save()
    return manifesto_obj
