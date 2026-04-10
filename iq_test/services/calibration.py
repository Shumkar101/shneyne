import random
from django.db.models import Count
from iq_test.models import Task

def find_next_best_task(available_tasks, last_task_type=None):
    """
    АЛГОРИТМ КАЛИБРОВКИ И БАЛАНСИРОВКИ
    Берет 1-ю и 2-ю задачи из каждого десятка (индексы 0, 1, 10, 11, 20, 21...)
    Чередует типы задач и выдает те, которые решали реже всего.
    """
    if not available_tasks.exists():
        return None

    # ШАГ 1: Находим "целевые" задачи (1-я и 2-я из каждого десятка)
    all_tasks = Task.objects.filter(is_active=True).order_by('task_type', 'id')
    
    target_task_ids = []
    current_type = None
    type_index = 0
    
    for task in all_tasks:
        if task.task_type != current_type:
            current_type = task.task_type
            type_index = 0
            
        # Математика десятков: остаток от деления на 10. 
        if type_index % 10 in (0, 1):
            target_task_ids.append(task.id)
            
        type_index += 1

    # ШАГ 2: Фильтруем доступные пользователю задачи, оставляя только целевые
    target_available = available_tasks.filter(id__in=target_task_ids)
    
    if not target_available.exists():
        target_available = available_tasks

    # ШАГ 3: Чередуем типы, чтобы картинки не казались одинаковыми
    filtered_tasks = target_available
    if last_task_type is not None:
        filtered_tasks = target_available.exclude(task_type=last_task_type)
        
    if not filtered_tasks.exists():
        filtered_tasks = target_available

    # ШАГ 4: Сортируем по количеству решений ВСЕМИ пользователями
    best_tasks = filtered_tasks.annotate(attempts=Count('answers')).order_by('attempts', 'id')
    
    if best_tasks.exists():
        min_attempts = best_tasks.first().attempts
        candidates = list(best_tasks.filter(attempts=min_attempts))
        return random.choice(candidates)
        
    return None