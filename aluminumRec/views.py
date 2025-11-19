from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta, datetime
from reportlab.pdfgen import canvas
from django.db.models import Sum, Q
import json
import pandas as pd

from .models import AluminumUser, ProductionRecord, ByProduct
from .predictor import predict_yield


# =============================================================
# ====================== REGISTER ==============================
# =============================================================
@csrf_exempt
def register(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            email = data.get('email')
            password = data.get('password')
            role = data.get('role', 'agent')

            if not name or not email or not password:
                return JsonResponse({"error": "Missing fields"}, status=400)

            if AluminumUser.objects.filter(email=email).exists():
                return JsonResponse({"error": "Email already registered"}, status=400)

            if len(password) < 6:
                return JsonResponse({"error": "Password must be at least 6 characters"}, status=400)

            if role == "admin" and AluminumUser.objects.filter(role="admin").exists():
                return JsonResponse({"error": "Admin already exists"}, status=400)

            AluminumUser.objects.create(
                name=name,
                email=email,
                password=make_password(password),
                role=role,
                is_approved=False,
            )

            return JsonResponse({"message": "Registered successfully. Waiting for admin approval."}, status=201)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)


# =============================================================
# ========================= LOGIN =============================
# =============================================================
@csrf_exempt
def login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')

            user = AluminumUser.objects.filter(email=email).first()
            if not user:
                return JsonResponse({"error": "User not found"}, status=404)

            if not check_password(password, user.password):
                return JsonResponse({"error": "Invalid password"}, status=401)

            if not user.is_approved:
                return JsonResponse({"error": "Your account is awaiting admin approval."}, status=403)

            redirect_map = {
                'admin': '/admin-dashboard',
                'agent': '/agent-dashboard',
                'scrap_team': '/scrap-dashboard',
            }

            return JsonResponse({
                "message": f"{user.role.capitalize()} login successful",
                "redirect": redirect_map[user.role]
            }, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)


# =============================================================
# ===================== PENDING USERS =========================
# =============================================================
@csrf_exempt
@require_http_methods(["GET"])
def pending_users(request):
    users = list(AluminumUser.objects.filter(is_approved=False).values("id", "name", "email", "role"))
    return JsonResponse(users, safe=False)


@csrf_exempt
@require_http_methods(["POST"])
def approve_user(request, user_id):
    try:
        user = AluminumUser.objects.get(id=user_id)
        user.is_approved = True
        user.save()
        return JsonResponse({"message": f"{user.name} approved successfully"})
    except AluminumUser.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)


# =============================================================
# ===================== PASSWORD RESET =======================
# =============================================================
@csrf_exempt
def forgot_password(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')

            user = AluminumUser.objects.filter(email=email).first()
            if not user:
                return JsonResponse({"error": "User not found"}, status=404)

            token = user.create_reset_token()
            return JsonResponse({"message": "Password reset token generated", "token": token})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)


@csrf_exempt
def reset_password(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            token = data.get('token')
            new_password = data.get('new_password')

            user = AluminumUser.objects.filter(reset_token=token).first()
            if not user:
                return JsonResponse({"error": "Invalid token"}, status=400)

            if timezone.now() - user.token_created_at > timedelta(minutes=10):
                return JsonResponse({"error": "Token expired"}, status=403)

            user.password = make_password(new_password)
            user.reset_token = None
            user.token_created_at = None
            user.save()

            return JsonResponse({"message": "Password reset successful"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)


# =============================================================
# ================== ML PREDICTION SAVE ========================
# =============================================================
@csrf_exempt
def predict_production(request):
    """
    Accepts POST JSON with:
    {
      email, bauxite_mass, caustic_soda_conc, temperature, pressure, purity, reaction_time
    }
    Creates a ProductionRecord and also creates a new ByProduct row for every prediction.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")

            # Validate required numeric fields — if missing will raise ValueError
            bauxite_mass = float(data.get("bauxite_mass", 0))
            caustic_soda_conc = float(data.get("caustic_soda_conc", 0))
            temperature = float(data.get("temperature", 0))
            pressure = float(data.get("pressure", 0))
            purity = float(data.get("purity", 0))
            reaction_time = float(data.get("reaction_time", 1.0))

            # Run ML model
            result = predict_yield(
                bauxite_mass,
                caustic_soda_conc,
                temperature,
                pressure,
                purity,
                reaction_time
            )

            if "error" in result:
                return JsonResponse(result, status=500)

            # Find agent (may be None if not found)
            user = AluminumUser.objects.filter(email=email, role="agent").first()

            # Create production record (even if user is None, we record it)
            record = ProductionRecord.objects.create(
                agent=user,
                bauxite_mass=bauxite_mass,
                caustic_soda_conc=caustic_soda_conc,
                temperature=temperature,
                pressure=pressure,
                ore_quality=purity,
                reaction_time=reaction_time,
                predicted_aluminum=result["predicted_yield"],
                predicted_byproduct=result["predicted_byproduct"],
            )

            # ALWAYS create a NEW ByProduct row for every prediction
            # This preserves history and allows Scrap Team to see all predictions.
            ByProduct.objects.create(
                name="Red Mud",
                quantity_kg=(result["predicted_byproduct"] / 100.0) * bauxite_mass if bauxite_mass else result["predicted_byproduct"],
                percent_of_total=result["predicted_byproduct"],
                status="received",
                source_prediction=record,
                assigned_to_email="",
                assigned_to_name="",
                remarks="Auto-created from agent prediction"
            )

            # Return prediction to frontend (percent values plus status)
            return JsonResponse({
                "predicted_yield": result["predicted_yield"],
                "predicted_byproduct": result["predicted_byproduct"],
                "status": "success"
            })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)


# =============================================================
# ====================== ADMIN SUMMARY ========================
# =============================================================
@csrf_exempt
def admin_summary(request):
    total_users = AluminumUser.objects.filter(is_approved=True).count()
    total_predictions = ProductionRecord.objects.count()

    records = ProductionRecord.objects.select_related("agent").order_by("-created_at")[:20]

    data = [
        {
            "agent": r.agent.name if r.agent else "Unknown",
            "email": r.agent.email if r.agent else "unknown",
            "temperature": r.temperature,
            "ore_quality": r.ore_quality,
            "reaction_time": r.reaction_time,
            "predicted_aluminum": r.predicted_aluminum,
            "predicted_byproduct": r.predicted_byproduct,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in records
    ]

    return JsonResponse({
        "total_users": total_users,
        "total_predictions": total_predictions,
        "recent_records": data
    })

@csrf_exempt
@require_http_methods(["POST"])
def reject_user(request, user_id):
    try:
        user = AluminumUser.objects.get(id=user_id)
        user.delete()   # Remove user completely
        return JsonResponse({"message": "User rejected and deleted"})
    except AluminumUser.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

# =============================================================
# ======================== USER COUNT =========================
# =============================================================
@csrf_exempt
def users_count(request):
    total = AluminumUser.objects.filter(is_approved=True).count()
    agents = AluminumUser.objects.filter(is_approved=True, role="agent").count()
    scrap_team = AluminumUser.objects.filter(is_approved=True, role="scrap_team").count()
    admins = AluminumUser.objects.filter(is_approved=True, role="admin").count()

    return JsonResponse({
        "total": total,
        "agents": agents,
        "scrap_team": scrap_team,
        "admins": admins,
    })


# =============================================================
# ===================== AGENT PREDICTIONS ======================
# =============================================================
@csrf_exempt
def agent_predictions(request):
    records = ProductionRecord.objects.select_related("agent").order_by("-created_at")

    data = [
        {
            "email": r.agent.email if r.agent else "unknown",
            "agent_name": r.agent.name if r.agent else "Unknown",
            "bauxite_mass": r.bauxite_mass,
            "caustic_soda_conc": r.caustic_soda_conc,
            "temperature": r.temperature,
            "pressure": r.pressure,
            "purity": r.ore_quality,
            "reaction_time": r.reaction_time,
            "predicted_yield": r.predicted_aluminum,
            "predicted_byproduct": r.predicted_byproduct,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in records
    ]

    return JsonResponse(data, safe=False)


# =============================================================
# ===================== RECENT APPROVED USERS ==================
# =============================================================
@csrf_exempt
@require_http_methods(["GET"])
def recent_approved_users(request):
    users = list(
        AluminumUser.objects.filter(is_approved=True)
        .order_by("-id")
        .values("id", "name", "email", "role")[:5]
    )
    return JsonResponse(users, safe=False)


# =============================================================
# ====================== PDF DOWNLOAD =========================
# =============================================================
def download_report(request):
    email = request.GET.get("email", "-")
    bauxite_mass = request.GET.get("bauxite_mass", "-")
    caustic_soda_conc = request.GET.get("caustic_soda_conc", "-")
    temperature = request.GET.get("temperature", "-")
    pressure = request.GET.get("pressure", "-")
    purity = request.GET.get("purity", "-")
    reaction_time = request.GET.get("reaction_time", "-")
    predicted_yield = request.GET.get("predicted_yield", "-")
    predicted_byproduct = request.GET.get("predicted_byproduct", "-")
    aluminum_kg = request.GET.get("aluminum_kg", "-")
    byproduct_kg = request.GET.get("byproduct_kg", "-")
    byproduct_name = request.GET.get("byproduct_name", "Red Mud")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="prediction_report.pdf"'

    p = canvas.Canvas(response)

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 800, "Aluminum Yield Prediction Report")

    p.setFont("Helvetica", 12)
    y = 770

    def write(label, value):
        nonlocal y
        p.drawString(50, y, f"{label}: {value}")
        y -= 22

    write("User", email)
    write("Bauxite Mass (kg)", bauxite_mass)
    write("Caustic Soda Concentration (%)", caustic_soda_conc)
    write("Temperature (°C)", temperature)
    write("Pressure (atm)", pressure)
    write("Purity (%)", purity)
    write("Reaction Time (hrs)", reaction_time)

    p.setFont("Helvetica-Bold", 12)
    write("----- Prediction Results -----", "")
    p.setFont("Helvetica", 12)

    write("Predicted Aluminum Yield (%)", predicted_yield)
    write("Predicted By-Product (%)", predicted_byproduct)
    write("Aluminum Output (kg)", aluminum_kg)
    write("By-Product Output (kg)", byproduct_kg)
    write("By-Product Name", byproduct_name)

    write("Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    p.showPage()
    p.save()
    return response


# =============================================================
# ====================== SCRAP TEAM APIs =======================
# =============================================================
@csrf_exempt
def byproducts(request):
    """Return all byproducts or by status."""
    status = request.GET.get("status")

    if status:
        items = ByProduct.objects.filter(status=status).order_by("-created_at")
    else:
        items = ByProduct.objects.all().order_by("-created_at")

    data = [
        {
            "id": item.id,
            "name": item.name,
            "quantity_kg": item.quantity_kg,
            "percent_of_total": item.percent_of_total,
            "status": item.status,
            "source_prediction_id": item.source_prediction.id if item.source_prediction else None,
            "assigned_to_email": item.assigned_to_email,
            "assigned_to_name": item.assigned_to_name,
            "remarks": item.remarks,
            "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": item.updated_at.strftime("%Y-%m-%d %H:%M"),
        }
        for item in items
    ]

    return JsonResponse(data, safe=False)


@csrf_exempt
def byproduct_summary(request):
    total_kg = ByProduct.objects.aggregate(total=Sum("quantity_kg"))["total"] or 0

    counts = {
        "received": ByProduct.objects.filter(status="received").count(),
        "in_process": ByProduct.objects.filter(status="in_process").count(),
        "used": ByProduct.objects.filter(status="used").count(),
    }

    return JsonResponse({
        "total_quantity_kg": total_kg,
        "counts": counts
    })


@csrf_exempt
def update_byproduct(request, bid):
    """Update status of a specific byproduct."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=400)

    try:
        item = ByProduct.objects.get(id=bid)
        body = json.loads(request.body)

        item.status = body.get("status", item.status)
        item.updated_at = timezone.now()
        item.save()

        return JsonResponse({"message": "Updated"})

    except ByProduct.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)


# NEW: return latest created byproduct
@csrf_exempt
def last_byproduct(request):
    item = ByProduct.objects.order_by("-created_at").first()
    if not item:
        return JsonResponse({}, status=200)
    data = {
        "id": item.id,
        "name": item.name,
        "quantity_kg": item.quantity_kg,
        "percent_of_total": item.percent_of_total,
        "status": item.status,
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": item.updated_at.strftime("%Y-%m-%d %H:%M"),
        "source_prediction_id": item.source_prediction.id if item.source_prediction else None,
    }
    return JsonResponse(data)


# NEW: return last processed (in_process or used)
@csrf_exempt
def last_processed_byproduct(request):
    item = ByProduct.objects.filter(Q(status="in_process") | Q(status="used")).order_by("-updated_at").first()
    if not item:
        return JsonResponse({}, status=200)
    data = {
        "id": item.id,
        "name": item.name,
        "quantity_kg": item.quantity_kg,
        "percent_of_total": item.percent_of_total,
        "status": item.status,
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": item.updated_at.strftime("%Y-%m-%d %H:%M"),
        "source_prediction_id": item.source_prediction.id if item.source_prediction else None,
    }
    return JsonResponse(data)
