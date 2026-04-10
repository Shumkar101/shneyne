from django.contrib import admin
from django.urls import path, include  # ПРОВЕРЬ: include должен быть импортирован!
from django.conf import settings
from django.conf.urls.static import static
from iq_test.views import register_view, profile_view

urlpatterns = [
    # 1. Панель управления (уже работает у тебя)
    path('admin/', admin.site.urls),
    # Авторизация (Django берет логин и логаут на себя)
    path('accounts/', include('django.contrib.auth.urls')), 
    
    # Наши новые пути
    path('register/', register_view, name='register'),
    path('profile/', profile_view, name='profile'),
    
    # 2. ПОДКЛЮЧЕНИЕ ТВОЕГО ПРИЛОЖЕНИЯ
    # Эта строка говорит Django: "Все запросы, которые не начинаются с admin/, 
    # ищи в файле iq_test/urls.py"
    path('', include('iq_test.urls')),
]

# Настройка для отображения картинок (SVG) во время разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)