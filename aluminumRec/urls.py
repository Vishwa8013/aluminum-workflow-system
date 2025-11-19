from django.urls import path
from . import views

urlpatterns = [

    # ---------------- AUTH ----------------
    path("register/", views.register, name="register"),
    path("login/", views.login, name="login"),

    # ---------------- APPROVALS ----------------
    path("pending-users/", views.pending_users, name="pending_users"),
    path("approve-user/<int:user_id>/", views.approve_user, name="approve_user"),

    # ---------------- PASSWORD ----------------

    # ---------------- PREDICTION ----------------
    path("predict_production/", views.predict_production, name="predict_production"),
    path("agent-predictions/", views.agent_predictions, name="agent_predictions"),

    # ---------------- ADMIN ----------------
    path("admin-summary/", views.admin_summary, name="admin_summary"),
    path("users-count/", views.users_count, name="users_count"),
    path("recent-approved-users/", views.recent_approved_users, name="recent_approved_users"),
    path("reject-user/<int:user_id>/", views.reject_user, name="reject_user"),


    # ---------------- SCRAP TEAM ----------------
 path("byproducts/", views.byproducts, name="byproducts"),
    path("byproducts/update-status/<int:bid>/", views.update_byproduct, name="update_byproduct"),
    path("byproducts/last/", views.last_byproduct, name="last_byproduct"),
    path("byproducts/summary/", views.byproduct_summary, name="byproduct_summary"),

    path("byproducts/last-processed/", views.last_processed_byproduct, name="last_processed_byproduct"),

    # ---------------- PDF DOWNLOAD ----------------
    path("download-report/", views.download_report, name="download_report"),
]
