from django.urls import path
from . import views

urlpatterns = [
    path('', views.chart, name='chart'),
    path('auto_update/', views.auto_update, name='chart_upd'),
    path('time_update/', views.time_update, name='time')
]
