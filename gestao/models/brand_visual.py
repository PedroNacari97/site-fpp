from django.db import models


class BrandVisual(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    primary_color = models.CharField(max_length=50)
    visual_description = models.TextField()
    logo = models.ImageField(upload_to="brands/logos/", null=True, blank=True)

    def __str__(self):
        return self.name
