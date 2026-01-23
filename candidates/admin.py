from django.contrib import admin
from .models import Candidate, Manifesto, QueryLog, ResearchAnalysis

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'party', 'province', 'is_active', 'is_featured', 'view_count', 'search_count')
    list_filter = ('province', 'party', 'is_active', 'is_featured')
    search_fields = ('name', 'party', 'bio')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('-view_count', 'name')
    actions = ['make_featured', 'make_active']

    def make_featured(self, request, queryset):
        queryset.update(is_featured=True)
    make_featured.short_description = "Mark selected candidates as featured"

    def make_active(self, request, queryset):
        queryset.update(is_active=True)
    make_active.short_description = "Mark selected candidates as active"

@admin.register(Manifesto)
class ManifestoAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'uploaded_at')
    search_fields = ('candidate__name', 'vision_summary', 'key_promises')
    list_filter = ('uploaded_at',)

@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ('query', 'source', 'timestamp')
    list_filter = ('source', 'timestamp')
    search_fields = ('query', 'response')
    readonly_fields = ('timestamp',)

@admin.register(ResearchAnalysis)
class ResearchAnalysisAdmin(admin.ModelAdmin):
    list_display = ('title', 'documents_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'analysis_content')
    readonly_fields = ('created_at',)
