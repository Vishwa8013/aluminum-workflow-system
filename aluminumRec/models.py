from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
import uuid


# ==============================
# USER
# ==============================
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user


class AluminumUser(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("agent", "Agent"),
        ("scrap_team", "Scrap Team"),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_approved = models.BooleanField(default=False)

    # reset token
    reset_token = models.CharField(max_length=100, null=True, blank=True)
    token_created_at = models.DateTimeField(null=True, blank=True)

    def create_reset_token(self):
        token = uuid.uuid4().hex
        self.reset_token = token
        self.token_created_at = timezone.now()
        self.save()
        return token

    def __str__(self):
        return self.email


# ==============================
# PRODUCTION PREDICTION RECORD
# ==============================
class ProductionRecord(models.Model):
    agent = models.ForeignKey(
        AluminumUser, on_delete=models.SET_NULL, null=True, blank=True
    )

    bauxite_mass = models.FloatField()
    caustic_soda_conc = models.FloatField()
    temperature = models.FloatField()
    pressure = models.FloatField()
    ore_quality = models.FloatField()
    reaction_time = models.FloatField()

    predicted_aluminum = models.FloatField()
    predicted_byproduct = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Record {self.id} - {self.agent}"


# ==============================
# BY-PRODUCT
# ==============================
class ByProduct(models.Model):
    STATUS = [
        ("received", "Received"),
        ("in_process", "In Process"),
        ("used", "Used"),
    ]

    name = models.CharField(max_length=100, default="Red Mud")

    source_prediction = models.ForeignKey(
        ProductionRecord, on_delete=models.CASCADE, null=True, blank=True
    )

    quantity_kg = models.FloatField(default=0)
    percent_of_total = models.FloatField(default=0)

    status = models.CharField(
        max_length=20, choices=STATUS, default="received"
    )

    assigned_to_email = models.CharField(max_length=100, null=True, blank=True)
    assigned_to_name = models.CharField(max_length=100, null=True, blank=True)

    remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.quantity_kg}kg"
