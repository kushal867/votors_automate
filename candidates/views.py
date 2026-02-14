from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db import models
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
import json
import logging

from .models import Candidate, Manifesto, QueryLog, ResearchAnalysis, EngagementHistory
from django.db.models import Sum, Q, F
from django.utils import timezone
from .utils import (
    analyze_candidate_data, 
    analyze_manifesto_vision, 
    extract_text_from_pdf, 
    get_chatbot_response,
    get_ai_response,
    analyze_multiple_manifestos,
    calculate_sentiment,
    parse_structured_response
)
from .services import get_relevant_context, process_manifesto_upload
from .analytics import (
    get_dashboard_stats, 
    get_trending_topics, 
    get_sentiment_velocity, 
    get_system_activity,
    get_political_briefing
)

logger = logging.getLogger(__name__)

class CandidateListView(ListView):
    model = Candidate
    template_name = 'candidates/candidate_list.html'
    context_object_name = 'candidates'

    def get_queryset(self):
        queryset = super().get_queryset()
        province = self.request.GET.get('province')
        if province:
            queryset = queryset.filter(province=province)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['provinces'] = Candidate.PROVINCE_CHOICES
        context['selected_province'] = self.request.GET.get('province')
        return context

class CandidateDetailView(DetailView):
    model = Candidate
    template_name = 'candidates/candidate_detail.html'
    context_object_name = 'candidate'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Track engagement
        self.object.view_count = models.F('view_count') + 1
        self.object.save(update_fields=['view_count'])
        
        # Log to EngagementHistory
        EngagementHistory.objects.create(candidate=self.object, views=1)
        
        context['manifestos'] = self.object.manifestos.all()
        
        # Add Related Assets
        context['related_candidates'] = Candidate.objects.filter(
            models.Q(party=self.object.party) | models.Q(province=self.object.province)
        ).exclude(id=self.object.id).distinct()[:4]
        
        # Intelligence Enrichment: Sentiment Snapshot
        if self.object.ai_work_analysis:
            context['sentiment_score'] = int((calculate_sentiment(self.object.ai_work_analysis) + 1) * 50)
        else:
            context['sentiment_score'] = 75 # Baseline
            
        # Get real trend if possible, otherwise fallback
        history = EngagementHistory.objects.filter(candidate=self.object).order_by('timestamp')[:7]
        if history.count() >= 3:
            context['engagement_trend'] = [h.views for h in history]
        else:
            context['engagement_trend'] = [20, 35, 45, 30, 55, 70, 85] # Mock baseline
            
        return context

class CandidateCreateView(CreateView):
    model = Candidate
    fields = ['name', 'party', 'image', 'bio', 'past_work']
    template_name = 'candidates/candidate_form.html'
    success_url = reverse_lazy('candidate-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        try:
            self.object.ai_work_analysis = analyze_candidate_data(self.object)
            self.object.save()
        except Exception as e:
            logger.error(f"Error analyzing candidate data: {e}")
        return response

class CandidateUpdateView(UpdateView):
    model = Candidate
    fields = ['name', 'party', 'image', 'bio', 'past_work', 'is_active', 'is_featured']
    template_name = 'candidates/candidate_form.html'
    success_url = reverse_lazy('candidate-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        if 'past_work' in form.changed_data:
            try:
                self.object.ai_work_analysis = analyze_candidate_data(self.object)
                self.object.save()
            except Exception as e:
                logger.error(f"Error re-analyzing candidate data: {e}")
        return response

class CandidateDeleteView(DeleteView):
    model = Candidate
    template_name = 'candidates/candidate_confirm_delete.html'
    success_url = reverse_lazy('candidate-list')

def upload_manifesto(request, candidate_id):
    candidate = get_object_or_404(Candidate, id=candidate_id)
    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf_file')
        if pdf_file:
            try:
                manifesto = Manifesto.objects.create(candidate=candidate, pdf_file=pdf_file)
                text = extract_text_from_pdf(pdf_file)
                analysis_raw = analyze_manifesto_vision(text, candidate.name)
                
                # Use service to process and save
                process_manifesto_upload(manifesto, analysis_raw, text)
                
                messages.success(request, f"Manifesto for {candidate.name} uploaded and intelligence report generated.")
                return redirect('candidate-detail', pk=candidate.id)
            except Exception as e:
                logger.error(f"Upload/Analysis Error: {e}")
                messages.error(request, f"Error processing manifesto: {str(e)}")
                
    return render(request, 'candidates/upload_manifesto.html', {'candidate': candidate})

def chat_view(request):
    """
    Main AI Chat interface for Voter Vision.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_query = data.get('query', '').strip()
            
            if not user_query:
                return JsonResponse({'status': 'error', 'message': 'Query cannot be empty.'}, status=400)

            # 1. Gather context using service
            local_context, web_results = get_relevant_context(user_query)
            
            # 2. Get history from session
            history = request.session.get('chat_history', [])
            
            # 3. Get AI Response
            bot_response = get_chatbot_response(
                user_query=user_query, 
                context_data=local_context, 
                history=history,
                web_results=web_results
            )
            
            print(f"DEBUG: AI Response received: {bot_response[:100]}...")
            
            # 4. Update session history
            history.append({'role': 'user', 'content': user_query})
            history.append({'role': 'assistant', 'content': bot_response})
            request.session['chat_history'] = history[-10:] # Keep last 5 rounds

            # 5. Log Query
            sentiment = calculate_sentiment(user_query + " " + bot_response)
            QueryLog.objects.create(
                query=user_query, 
                response=bot_response, 
                sentiment_score=sentiment,
                source='Strategic Core'
            )
            
            return JsonResponse({'status': 'success', 'response': bot_response})
            
        except Exception as e:
            logger.exception("Chat view error: ")
            return JsonResponse({'status': 'error', 'message': "I encountered a processing error. Please try a different query."}, status=500)
    
    return render(request, 'candidates/chat.html')

def compare_candidates(request):
    """
    Simple side-by-side comparison of two candidates.
    """
    candidate_ids = request.GET.getlist('compare')
    candidates = Candidate.objects.filter(id__in=candidate_ids).prefetch_related('manifestos')
    
    ai_comparison = None
    if len(candidates) == 2:
        c1, c2 = candidates[0], candidates[1]
        m1 = c1.manifestos.last()
        m2 = c2.manifestos.last()
        
        if m1 and m2:
            prompt = f"""
            COMPARE TWO CANDIDATES:
            
            CANDIDATE 1: {c1.name} ({c1.party})
            Manifesto Highlights: {m1.vision_summary}
            
            CANDIDATE 2: {c2.name} ({c2.party})
            Manifesto Highlights: {m2.vision_summary}
            
            Please provide a comparative analysis focusing on:
            - Policy Priorities
            - Economic Feasibility
            - Public Record Contrast
            """
            ai_comparison = get_ai_response(prompt, system_instruction="You are a neutral Election Analyst.")
            
    return render(request, 'candidates/compare.html', {
        'candidates': candidates,
        'ai_comparison': ai_comparison
    })

def global_search(request):
    query = request.GET.get('q', '').strip()
    candidates = []
    if query:
        candidates = Candidate.objects.filter(
            models.Q(name__icontains=query) | 
            models.Q(party__icontains=query) |
            models.Q(bio__icontains=query)
        )
        # Track engagement for matched candidates
        candidates.update(search_count=models.F('search_count') + 1)
        
        # Log search engagement
        for c in candidates:
            EngagementHistory.objects.create(candidate=c, searches=1)

    return render(request, 'candidates/candidate_list.html', {
        'candidates': candidates,
        'search_query': query,
        'is_search': True
    })

def analysis_lab(request):
    """
    The Research Lab: Independent document analysis with context-aware chat.
    """
    # AJAX Chat in the Lab
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            user_query = data.get('query')
            
            # Use specific namespace for isolation
            doc_context = request.session.get('research_lab_context', 'No document context available.')
            lab_history = request.session.get('research_lab_history', [])
            
            history_str = ""
            if lab_history:
                history_str = "\n".join([f"{'User' if m['role'] == 'user' else 'Analyst'}: {m['content']}" for m in lab_history[-4:]])
            
            prompt = f"""
            RESEARCH CONTEXT (The Documents):
            {doc_context[:20000]} 
            
            CONVERSATION HISTORY:
            {history_str or 'First query.'}
            
            USER RESEARCH QUERY:
            {user_query}
            
            INSTRUCTIONS:
            - Analyze the query ONLY using the provided RESEARCH CONTEXT.
            - Provide a technical, objective response.
            - If data is missing, suggest what information is needed from the user.
            """
            
            response = get_ai_response(prompt, system_instruction="You are a Senior Document Intelligence Analyst.")
            
            # Update isolation lab history
            lab_history.append({'role': 'user', 'content': user_query})
            lab_history.append({'role': 'assistant', 'content': response})
            request.session['research_lab_history'] = lab_history[-6:]
            
            # Log Query
            sentiment = calculate_sentiment(user_query + " " + response)
            QueryLog.objects.create(
                query=user_query, 
                response=response, 
                sentiment_score=sentiment,
                source='Ghoshana Lab Chat'
            )

            return JsonResponse({'status': 'success', 'response': response})
        except Exception as e:
            logger.error(f"Lab Chat Error: {e}")
            return JsonResponse({'status': 'error', 'response': "The lab system is offline or overloaded."}, status=500)

    analysis_result = None
    candidates = Candidate.objects.all()
    
    # Action: Clear History
    if request.GET.get('clear') == '1':
        request.session['research_lab_history'] = []
        request.session['research_lab_context'] = ""
        request.session['research_lab_last_result'] = None
        messages.info(request, "Research lab context cleared.")
        return redirect('analysis-lab')

    if request.method == 'POST':
        files = request.FILES.getlist('manifestos')
        selected_candidate_ids = request.POST.getlist('selected_candidates')
        
        if files or selected_candidate_ids:
            documents = []
            context_for_session = ""
            
            # Process uploaded files
            for f in files[:2]: 
                try:
                    text = extract_text_from_pdf(f)
                    documents.append({'name': f.name, 'text': text})
                    context_for_session += f"\nFILE: {f.name}\nCONTENT: {text[:10000]}\n"
                except Exception as e:
                    logger.error(f"Error processing {f.name}: {e}")
            
            # Process selected candidates from DB
            for cid in selected_candidate_ids:
                try:
                    candidate = Candidate.objects.get(id=cid)
                    manifesto = candidate.manifestos.first() # Get the latest/first manifesto
                    if manifesto and manifesto.pdf_file:
                        text = extract_text_from_pdf(manifesto.pdf_file)
                        documents.append({'name': f"Candidate: {candidate.name}", 'text': text})
                        context_for_session += f"\nCANDIDATE: {candidate.name}\nCONTENT: {text[:10000]}\n"
                except Exception as e:
                    logger.error(f"Error processing candidate {cid}: {e}")
            
            # Limit to top 2 documents total for meaningful comparison
            documents = documents[:2]
            
            if documents:
                request.session['research_lab_context'] = context_for_session
                request.session['research_lab_history'] = [] 
                
                analysis_result = analyze_multiple_manifestos(documents)
                request.session['research_lab_last_result'] = analysis_result
                
                # Save Persistent Analysis
                doc_titles = ", ".join([doc['name'] for doc in documents])
                ResearchAnalysis.objects.create(
                    title=f"Comparative Analysis: {doc_titles}",
                    documents_count=len(documents),
                    analysis_content=analysis_result,
                    context_used=context_for_session[:5000] # Save first 5k chars of context
                )

                messages.success(request, f"Intelligence gathered for {len(documents)} documents. Analysis complete.")
            else:
                messages.warning(request, "No valid document data found.")

    return render(request, 'candidates/analysis_lab.html', {
        'analysis_result': analysis_result or request.session.get('research_lab_last_result'),
        'candidates': candidates,
        'previous_analyses': ResearchAnalysis.objects.all().order_by('-created_at')[:10]
    })

def dashboard_view(request):
    """
    The Command Center Dashboard: High-level overview of system intelligence with live data.
    """
    # 1. Core Analytics via Service
    stats = get_dashboard_stats()
    activities = get_system_activity()
    sentiment_data = get_sentiment_velocity()
    trending_topics = get_trending_topics()
    news_briefing = get_political_briefing()
    
    # 2. Featured Content
    featured_candidate = Candidate.objects.filter(is_featured=True).first() or \
                         Candidate.objects.filter(image__isnull=False).first() or \
                         Candidate.objects.first()
    
    # 3. Geographic Intelligence
    province_counts = Candidate.objects.values('province').annotate(count=models.Count('province'))
    province_stats = {str(i): 0 for i in range(1, 8)}
    for p in province_counts:
        province_stats[p['province']] = p['count']

    # 4. Leading Assets
    popular_candidates = Candidate.objects.filter(is_active=True).order_by('-view_count')[:5]

    return render(request, 'candidates/dashboard.html', {
        'stats': stats,
        'recent_candidates': Candidate.objects.all().order_by('-created_at')[:5],
        'popular_candidates': popular_candidates,
        'featured_candidate': featured_candidate,
        'activities': activities,
        'province_stats': province_stats,
        'trending_topics': trending_topics,
        'sentiment_data': sentiment_data,
        'news_briefing': news_briefing,
        'current_time': timezone.now(),
        'provinces': Candidate.PROVINCE_CHOICES
    })


def candidate_report_view(request, pk):
    """
    Generates a high-level comprehensive intelligence report for a candidate.
    """
    candidate = get_object_or_404(Candidate, pk=pk)
    manifestos = candidate.manifestos.all()
    
    # Check if we should re-generate intelligence
    regenerate = request.GET.get('refresh') == '1'
    
    report_content = None
    if not regenerate:
        # Try to use existing analysis if available
        report_content = candidate.ai_work_analysis
    
    if not report_content or regenerate:
        prompt = f"""
        GENERATE COMPREHENSIVE STRATEGIC INTELLIGENCE REPORT
        
        ASSET: {candidate.name}
        PARTY: {candidate.party}
        BIO: {candidate.bio}
        PAST WORK: {candidate.past_work}
        
        NUM DOCUMENTS LOGGED: {manifestos.count()}
        
        TASK:
        Provide a multi-dimensional analysis including:
        1. STRATEGIC POSITIONING: Where does this candidate stand in the current political landscape?
        2. ELECTORAL VIABILITY: Strengths and potential obstacles.
        3. POLICY CONSISTENCY: (If manifestos exist) How consistent is their current vision with past work?
        4. PUBLIC SENTIMENT SNAPSHOT: Based on general political knowledge (AI Internal).
        5. RECOMMENDATION: Brief closing summary for a neutral voter.
        
        CRITICAL: You MUST also provide a strategic breakdown in JSON format at the VERY END of your response inside a ```json ``` block with exactly these keys (scores 0-100):
        {{
            "strategic_matrix": {{
                "economic_vision": score,
                "social_progress": score,
                "political_stability": score,
                "infrastructure_focus": score,
                "diplomatic_acumen": score
            }}
        }}
        
        Format the body as a formal intelligence briefing with sections.
        """
        raw_response = get_ai_response(prompt, system_instruction="You are a Lead Intelligence Analyst for Voter Vision Nepal.")
        
        # Parse the JSON out of the response if it exists
        # Parse the JSON out of the response if it exists
        matrix_data = parse_structured_response(raw_response)
        
        # Clean the response for display (remove the JSON block)
        import re
        report_content = re.sub(r'```json\s*.*?\s*```', '', raw_response, flags=re.DOTALL).strip()
        
        candidate.ai_work_analysis = report_content
        # We can store the matrix in a temporary context or session, 
        # but for simplicity let's just use it in this request context.
        context_matrix = matrix_data.get('strategic_matrix') if matrix_data else None
        
        candidate.save()
    else:
        # If we have report_content but no matrix, we might want to default or skip
        context_matrix = {
            "economic_vision": 75,
            "social_progress": 82,
            "political_stability": 65,
            "infrastructure_focus": 70,
            "diplomatic_acumen": 60
        } # Baseline defaults

    return render(request, 'candidates/candidate_report.html', {
        'candidate': candidate,
        'report_content': report_content,
        'manifestos': manifestos,
        'strategic_matrix': context_matrix,
        'current_time': timezone.now()
    })

