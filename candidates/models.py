from django.db import models

class Candidate(models.Model):
    name = models.CharField(max_length=200)
    party = models.CharField(max_length=200)
    image = models.ImageField(upload_to='candidates/', null=True, blank=True)
    bio = models.TextField()
    past_work = models.TextField(help_text="Describe past accomplishments and projects")
    ai_work_analysis = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.party})"

class Manifesto(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='manifestos')
    pdf_file = models.FileField(upload_to='manifestos/')
    vision_summary = models.TextField(null=True, blank=True)
    key_promises = models.TextField(null=True, blank=True)
    ai_vision_analysis = models.TextField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Manifesto of {self.candidate.name}"
