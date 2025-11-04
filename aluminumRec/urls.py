from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.register),
    path("login/", views.login),
    path("pending-users/", views.pending_users),
    path("approve-user/<int:user_id>/", views.approve_user),
  
    path("predict_production/", views.predict_production, name="predict_production"),
    path("admin-summary/", views.admin_summary),
    path("users-count/", views.users_count),
    path("agent-predictions/", views.agent_predictions),
    path("recent-approved-users/", views.recent_approved_users),

]
