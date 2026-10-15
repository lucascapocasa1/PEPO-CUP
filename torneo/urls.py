from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('torneos/', views.torneo_lista, name='torneo_lista'),
    path('torneo/<slug:slug>/', views.torneo_detalle, name='torneo_detalle'),
    path('torneo/<slug:slug>/participantes/', views.participantes, name='participantes'),
    path('torneo/<slug:slug>/participante/<int:pk>/', views.participante_detalle, name='participante_detalle'),
    path('torneo/<slug:slug>/partidos/', views.partidos, name='partidos'),
    path('torneo/<slug:slug>/goleadores/', views.goleadores, name='goleadores'),
    path('partido/<int:pk>/', views.partido_detalle, name='partido_detalle'),

    # Organizador
    path('cargar/', views.cargar, name='cargar'),
    path('cargar/partido/<int:pk>/', views.cargar_partido, name='cargar_partido'),
    path('entrar/', auth_views.LoginView.as_view(template_name='torneo/login.html'), name='login'),
    path('salir/', auth_views.LogoutView.as_view(), name='logout'),
]
