from django.urls import path
from . import views

urlpatterns = [
    # Вот он - пустой путь для главной страницы!
    path('', views.index, name='index'), 
    
    # Наши API маршруты
    path('api/start/', views.start_session, name='start_session'),
    path('api/get_task/', views.get_next_task, name='get_next_task'),
    path('api/submit_answer/', views.submit_answer, name='submit_answer'),
]