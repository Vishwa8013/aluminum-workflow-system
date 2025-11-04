from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta
import json
from .models import AluminumUser, ProductionRecord
from .predictor import predict_yield


# -------------------- REGISTER --------------------
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


# -------------------- LOGIN --------------------
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


# -------------------- APPROVALS --------------------
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


# -------------------- PASSWORD RESET --------------------
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


# -------------------- ML PREDICTION --------------------
@csrf_exempt
def predict_production(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")

            bauxite_mass = float(data.get("bauxite_mass"))
            caustic_soda_conc = float(data.get("caustic_soda_conc"))
            temperature = float(data.get("temperature"))
            pressure = float(data.get("pressure"))
            purity = float(data.get("purity"))
            reaction_time = float(data.get("reaction_time", 1.0))

            result = predict_yield(bauxite_mass, caustic_soda_conc, temperature, pressure, purity, reaction_time)
            if "error" in result:
                return JsonResponse(result, status=500)

            user = AluminumUser.objects.filter(email=email, role="agent").first()
            if user:
                ProductionRecord.objects.create(
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

            return JsonResponse({
                "predicted_yield": result["predicted_yield"],
                "predicted_byproduct": result["predicted_byproduct"],
                "status": "success"
            })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)


# -------------------- ADMIN SUMMARY --------------------
@csrf_exempt
def admin_summary(request):
    total_users = AluminumUser.objects.filter(is_approved=True).count()
    total_predictions = ProductionRecord.objects.count()
    records = ProductionRecord.objects.select_related("agent").order_by("-created_at")[:20]

    data = [
        {
            "agent": r.agent.name,
            "email": r.agent.email,
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


# -------------------- UPDATED USERS COUNT (FIXED VERSION) --------------------
@csrf_exempt
def users_count(request):
    """Return total approved users by role."""
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


# -------------------- AGENT PREDICTIONS --------------------
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


# -------------------- RECENT APPROVED USERS --------------------
@csrf_exempt
@require_http_methods(["GET"])
def recent_approved_users(request):
    """Return the latest approved users for the admin overview."""
    users = list(
        AluminumUser.objects.filter(is_approved=True)
        .order_by("-id")
        .values("id", "name", "email", "role")[:5]
    )
    return JsonResponse(users, safe=False)

