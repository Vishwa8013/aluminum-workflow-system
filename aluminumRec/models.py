from django.db import models
from django.utils import timezone
import uuid


class AluminumUser(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('agent', 'Agent'),
        ('scrap_team', 'Scrap Team'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, max_length=190, null=True)
    password = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='agent')
    is_approved = models.BooleanField(default=False)
    reset_token = models.CharField(max_length=100, null=True, blank=True)
    token_created_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.role})"

    def create_reset_token(self):
        token = str(uuid.uuid4())
        self.reset_token = token
        self.token_created_at = timezone.now()
        self.save()
        return token


class ProductionRecord(models.Model):
    agent = models.ForeignKey(AluminumUser, on_delete=models.CASCADE, related_name="records")
    bauxite_mass = models.FloatField(default=0)
    caustic_soda_conc = models.FloatField(default=0)
    temperature = models.FloatField(default=0)
    pressure = models.FloatField(default=0)
    ore_quality = models.FloatField(default=0)
    reaction_time = models.FloatField(default=0)
    predicted_aluminum = models.FloatField(default=0)
    predicted_byproduct = models.FloatField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Production #{self.id} by {self.agent.name}"


# -------------------- NEW MODEL: BY-PRODUCT RECORD --------------------
class ByProductRecord(models.Model):
    STATUS_CHOICES = [
        ("received", "Received"),
        ("in_process", "In Process"),
        ("used", "Used"),
    ]

    source_prediction = models.ForeignKey(
        ProductionRecord, on_delete=models.CASCADE, related_name="byproducts"
    )
    name = models.CharField(max_length=100, default="Red Mud")
    quantity_kg = models.FloatField(default=0)
    percent_of_total = models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="received")
    assigned_to = models.ForeignKey(
        AluminumUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="byproduct_tasks",
        limit_choices_to={"role": "scrap_team"},
    )
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.status}) - {self.quantity_kg} kg"
