from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db import models
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
import json
import logging

from .models import Candidate, Manifesto, QueryLog, ResearchAnalysis
from .utils import (
    analyze_candidate_data, 
    analyze_manifesto_vision, 
    extract_text_from_pdf, 
    get_chatbot_response,
    get_ai_response,
    analyze_multiple_manifestos
)
from .services import get_relevant_context, process_manifesto_upload

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
        
        context['manifestos'] = self.object.manifestos.all()
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
            QueryLog.objects.create(query=user_query, response=bot_response, source='Strategic Core')
            
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
            QueryLog.objects.create(query=user_query, response=response, source='Ghosada Lab Chat')

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
    from django.utils import timezone
    from django.db.models import Sum

    total_candidates = Candidate.objects.count()
    total_manifestos = Manifesto.objects.count()
    total_views = Candidate.objects.aggregate(total_views=Sum('view_count'))['total_views'] or 0
    recent_candidates = Candidate.objects.all().order_by('-id')[:5]
    
    # Real-ish activity feed
    activities = []
    for cand in recent_candidates:
        activities.append({
            'type': 'Candidate Added',
            'detail': f"{cand.name} ({cand.party}) registered",
            'time': cand.created_at
        })
    
    stats = {
        'total_assets': total_candidates,
        'ingested_data': total_manifestos,
        'queries_processed': QueryLog.objects.count(),
        'global_reach': f"{total_views}+", # Live views from DB
        'system_status': 'Fully Operational',
        'last_sync': timezone.now().strftime("%Y.%m.%d %H:%M:%S")
    }
    
    # Enrich activities with Query Logs
    recent_queries = QueryLog.objects.all().order_by('-timestamp')[:5]
    for q in recent_queries:
        activities.append({
            'type': 'Intelligence Query',
            'detail': f"'{q.query[:30]}...' processed via {q.source}",
            'time': q.timestamp
        })
    
    # Get a featured candidate for the dashboard view
    featured_candidate = Candidate.objects.filter(is_featured=True).first() or \
                         Candidate.objects.filter(image__isnull=False).first() or \
                         Candidate.objects.first()
    
    # Calculate Province Distribution for the map
    province_counts = Candidate.objects.values('province').annotate(count=models.Count('province'))
    province_stats = {str(i): 0 for i in range(1, 8)}
    for p in province_counts:
        province_stats[p['province']] = p['count']

    # Popular Assets (Top Viewed)
    popular_candidates = Candidate.objects.filter(is_active=True).order_by('-view_count')[:4]

    # Trending Topics (Naive word frequency from QueryLog)
    all_queries = QueryLog.objects.all().order_by('-timestamp')[:100].values_list('query', flat=True)
    all_words = " ".join(all_queries).lower().split()
    stopwords = {'the', 'a', 'is', 'in', 'and', 'to', 'of', 'for', 'nepal', 'who', 'what', 'how', 'is', 'the', 'candidate', 'manifesto', 'election', 'voter', 'vision'}
    trending_words = {}
    for word in all_words:
        # Clean word (remove punctuation)
        word = ''.join(e for e in word if e.isalnum())
        if len(word) > 3 and word not in stopwords:
            trending_words[word] = trending_words.get(word, 0) + 1
    
    trending_topics = sorted(trending_words.items(), key=lambda x: x[1], reverse=True)[:5]
    trending_topics = [t[0].capitalize() for t in trending_topics]

    # Mock Sentiment Data for the chart
    sentiment_data = [45, 60, 75, 40, 85, 95] # Could be tied to query frequency or keywords

    return render(request, 'candidates/dashboard.html', {
        'stats': stats,
        'recent_candidates': recent_candidates,
        'popular_candidates': popular_candidates,
        'featured_candidate': featured_candidate,
        'activities': sorted(activities, key=lambda x: x['time'], reverse=True),
        'province_stats': province_stats,
        'trending_topics': trending_topics,
        'sentiment_data': sentiment_data,
        'current_time': timezone.now()
    })

