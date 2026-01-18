from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from .models import Candidate, Manifesto
from django.contrib import messages
from django.http import JsonResponse
from .utils import analyze_candidate_data, analyze_manifesto_vision, extract_text_from_pdf, get_chatbot_response
import json

class CandidateListView(ListView):
    model = Candidate
    template_name = 'candidates/candidate_list.html'
    context_object_name = 'candidates'

class CandidateDetailView(DetailView):
    model = Candidate
    template_name = 'candidates/candidate_detail.html'
    context_object_name = 'candidate'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['manifestos'] = self.object.manifestos.all()
        return context

class CandidateCreateView(CreateView):
    model = Candidate
    fields = ['name', 'party', 'image', 'bio', 'past_work']
    template_name = 'candidates/candidate_form.html'
    success_url = reverse_lazy('candidate-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.ai_work_analysis = analyze_candidate_data(self.object)
        self.object.save()
        return response

def upload_manifesto(request, candidate_id):
    candidate = get_object_or_404(Candidate, id=candidate_id)
    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf_file')
        if pdf_file:
            manifesto = Manifesto.objects.create(candidate=candidate, pdf_file=pdf_file)
            text = extract_text_from_pdf(pdf_file)
            analysis_raw = analyze_manifesto_vision(text, candidate.name)
            
            # Attempt to parse JSON if AI followed instructions
            try:
                import json
                # Strip markdown blocks if present
                clean_json = analysis_raw.strip()
                if clean_json.startswith('```json'):
                    clean_json = clean_json.split('```json')[1].split('```')[0].strip()
                elif clean_json.startswith('```'):
                    clean_json = clean_json.split('```')[1].split('```')[0].strip()
                    
                data = json.loads(clean_json)
                manifesto.vision_summary = data.get('summary', text[:500])
                manifesto.key_promises = data.get('promises', '')
                manifesto.ai_vision_analysis = data.get('full_analysis', analysis_raw)
            except:
                # Fallback to saving everything in analysis field
                manifesto.vision_summary = text[:500]
                manifesto.ai_vision_analysis = analysis_raw
            
            manifesto.save()
            messages.success(request, f"Manifesto uploaded and analyzed for {candidate.name}")
            return redirect('candidate-detail', pk=candidate.id)
    return render(request, 'candidates/upload_manifesto.html', {'candidate': candidate})

def chat_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_query = data.get('query', '')
            
            # 1. Gather relevant local context (Optimization: Prefetch manifestos and filter if possible)
            # For now, we prefetch to avoid N+1 queries. 
            # In a larger app, we'd use search to find only RELEVANT candidates.
            candidates = Candidate.objects.prefetch_related('manifestos').all()
            
            # Simple keyword matching to narrow down context if query mentions a candidate or party
            relevant_candidates = []
            query_lower = user_query.lower()
            for c in candidates:
                if (c.name.lower() in query_lower or 
                    c.party.lower() in query_lower or 
                    len(candidates) <= 3): # If few candidates, just include all
                    relevant_candidates.append(c)

            context_parts = []
            for c in relevant_candidates:
                c_info = f"Candidate: {c.name}, Party: {c.party}, Bio: {c.bio[:200]}... \n"
                c_info += f"AI Analysis: {c.ai_work_analysis or 'No analytical data yet'}. \n"
                # Use only the latest manifesto for context to save tokens
                m = c.manifestos.last()
                if m:
                    c_info += f"Manifesto Summary: {m.ai_vision_analysis or 'No manifesto analysis'}. \n"
                context_parts.append(c_info)
            
            local_context = "\n---\n".join(context_parts)
            
            # 2. Comprehensive Web Search (Triggered for candidates or specific keywords)
            web_context = ""
            political_keywords = ['news', 'recent', 'today', 'latest', 'election date', 'poll', 'who is', 'background', 'controversy', 'party', 'biography', 'history', 'record', 'manifesto', 'promise']
            
            # Search if keywords found OR if we identified specific candidates in the query
            if any(word in query_lower for word in political_keywords) or len(relevant_candidates) > 0:
                from .utils import web_search
                # Enhance query for better web results if a specific candidate is mentioned
                search_query = user_query
                if relevant_candidates and len(relevant_candidates) == 1:
                    search_query = f"{relevant_candidates[0].name} Nepal political background {user_query}"
                
                web_context = web_search(search_query)
            
            # 3. Combine contexts sparingly
            full_context = f"LOCAL INFO:\n{local_context or 'No specific candidate data found.'}"
            if web_context:
                full_context += f"\n\nWEB SEARCH RESULTS:\n{web_context}"
            
            # 4. Get Conversational History from session
            history = request.session.get('chat_history', [])
            
            bot_response = get_chatbot_response(user_query, full_context, history=history)
            
            # 5. Update history in session
            history.append({'role': 'user', 'content': user_query})
            history.append({'role': 'assistant', 'content': bot_response})
            # Limit history size to 10 messages for efficiency
            request.session['chat_history'] = history[-10:]
            
            return JsonResponse({'status': 'success', 'response': bot_response})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return render(request, 'candidates/chat.html')

def compare_candidates(request):
    candidate_ids = request.GET.getlist('compare')
    candidates = Candidate.objects.filter(id__in=candidate_ids)
    
    ai_comparison = None
    if len(candidates) == 2:
        c1, c2 = candidates[0], candidates[1]
        m1 = c1.manifestos.last()
        m2 = c2.manifestos.last()
        
        if m1 and m2:
            from .utils import get_ai_response
            prompt = f"""
            Compare these two candidates based on their Ghosada Patra (Manifesto):
            
            Candidate 1: {c1.name} ({c1.party})
            Manifesto Summary 1: {m1.ai_vision_analysis}
            
            Candidate 2: {c2.name} ({c2.party})
            Manifesto Summary 2: {m2.ai_vision_analysis}
            
            Provide a side-by-side comparison of their:
            1. Economic Vision
            2. Social Promises
            3. Unique selling points
            4. Feasibility comparison
            
            Format as a clear markdown table or structured sections.
            """
            ai_comparison = get_ai_response(prompt)
            
    return render(request, 'candidates/compare.html', {
        'candidates': candidates,
        'ai_comparison': ai_comparison
    })

def analysis_lab(request):
    """
    Independent analysis lab for 1 or 2 PDFs with interactive chat.
    Strictly isolated from main chat via 'research_lab_' session namespace.
    """
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Handle Chat Query via AJAX
        try:
            data = json.loads(request.body)
            user_query = data.get('query')
            # Use specific namespace to avoid collision with main chat
            doc_context = request.session.get('research_lab_context', 'No document context found.')
            lab_history = request.session.get('research_lab_history', [])
            
            history_str = "\n".join([f"{'User' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in lab_history[-4:]])
            
            from .utils import get_ai_response
            prompt = f"""
            ROLE: You are the DOCUMENT RESEARCH ANALYST (Internal Laboratory).
            TASK: Answer questions ONLY based on the uploaded Ghosada Patras provided below.
            
            GHOSADA PATRA CONTEXT:
            {doc_context}
            
            RESEARCH HISTORY:
            {history_str or 'Session started.'}
            
            USER QUERY:
            {user_query}
            
            INSTRUCTIONS:
            - Respond only based on the document text.
            - If data is missing, say 'Information not found in the provided documents'.
            - Keep analysis technical and accurate.
            """
            response = get_ai_response(prompt)
            
            # Update history
            lab_history.append({'role': 'user', 'content': user_query})
            lab_history.append({'role': 'assistant', 'content': response})
            request.session['research_lab_history'] = lab_history[-6:]
            
            return JsonResponse({'response': response})
        except Exception as e:
            return JsonResponse({'response': f"Signal Interrupted: {str(e)}"}, status=500)

    analysis_result = None
    if request.method == 'POST':
        # Handle PDF Upload
        files = request.FILES.getlist('manifestos')
        if files:
            documents = []
            context_for_session = ""
            for f in files[:2]:
                text = extract_text_from_pdf(f)
                documents.append({'name': f.name, 'text': text})
                context_for_session += f"\n--- RESEARCH DOC: {f.name} ---\n{text[:15000]}\n"
            
            # Persist in specific isolated session key
            request.session['research_lab_context'] = context_for_session
            request.session['research_lab_history'] = [] # Reset history for new docs
            from .utils import analyze_multiple_manifestos
            analysis_result = analyze_multiple_manifestos(documents)
            request.session['research_lab_last_result'] = analysis_result
            
    return render(request, 'candidates/analysis_lab.html', {
        'analysis_result': analysis_result or request.session.get('research_lab_last_result')
    })

