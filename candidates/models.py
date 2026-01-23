from django.db import models

class Candidate(models.Model):
    PROVINCE_CHOICES = [
        ('1', 'Koshi Province'),
        ('2', 'Madhesh Province'),
        ('3', 'Bagmati Province'),
        ('4', 'Gandaki Province'),
        ('5', 'Lumbini Province'),
        ('6', 'Karnali Province'),
        ('7', 'Sudurpashchim Province'),
    ]

    name = models.CharField(max_length=200)
    party = models.CharField(max_length=200)
    province = models.CharField(max_length=1, choices=PROVINCE_CHOICES, default='3')
    image = models.ImageField(upload_to='candidates/', null=True, blank=True)
    bio = models.TextField()
    past_work = models.TextField(help_text="Describe past accomplishments and projects")
    ai_work_analysis = models.TextField(null=True, blank=True)
    slug = models.SlugField(unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    search_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.party})"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Candidate.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

class Manifesto(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='manifestos')
    pdf_file = models.FileField(upload_to='manifestos/')
    vision_summary = models.TextField(null=True, blank=True)
    key_promises = models.TextField(null=True, blank=True)
    ai_vision_analysis = models.TextField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Manifesto of {self.candidate.name}"

class QueryLog(models.Model):
    query = models.TextField()
    response = models.TextField()
    source = models.CharField(max_length=50, default='Chat') # e.g., 'Chat', 'Lab'
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Query at {self.timestamp}"

class ResearchAnalysis(models.Model):
    title = models.CharField(max_length=255)
    documents_count = models.IntegerField(default=1)
    analysis_content = models.TextField()
    context_used = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analysis: {self.title} ({self.created_at})"
