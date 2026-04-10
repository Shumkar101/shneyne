from django.contrib import admin
from .models import Task, TestSession, AnswerLog

# Регистрируем модель Задач, чтобы управлять ими из админки
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    # Какие колонки показывать в общем списке
    list_display = ('id', 'task_type', 'correct_answer', 'estimated_weight', 'is_active')
    # Фильтры сбоку (например, показать только матрицы или только неактивные)
    list_filter = ('task_type', 'is_active')
    # Поиск по тексту задачи и ответу
    search_fields = ('text_content', 'correct_answer')

# Регистрируем Сессии
@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'age', 'sphere', 'started_at', 'completed_at')
    list_filter = ('sphere',)

# Регистрируем Логи ответов
@admin.register(AnswerLog)
class AnswerLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'task', 'user_answer', 'is_correct', 'time_spent_seconds')
    list_filter = ('is_correct', 'task__task_type')