import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Task, TestSession, AnswerLog
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required

# csrf_exempt используем для MVP, чтобы не мучаться с токенами при запросах из браузера
@csrf_exempt
def start_session(request):
    """Эндпоинт 1: Начало теста"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Создаем новую сессию
            session = TestSession.objects.create(
                age=data.get('age'),
                sphere=data.get('sphere'),
                estimated_ability=0.0, # Начинаем с нуля
                standard_error=3.0     # Высокая стартовая погрешность
            )
            return JsonResponse({'status': 'ok', 'session_id': str(session.id)})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

@csrf_exempt
@csrf_exempt
def get_next_task(request):
    """Эндпоинт 2: Выдача следующей задачи по алгоритму калибровки (балансировка)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            session_id = data.get('session_id')
            session = TestSession.objects.get(id=session_id)
            
            solved_task_ids = session.answers.values_list('task_id', flat=True)
            solved_count = len(solved_task_ids)
            
            TOTAL_QUESTIONS_LIMIT = 20
            
            # Вспомогательная функция для формирования ответа (чтобы не дублировать код)
            # Вспомогательная функция для формирования ответа
            def get_finished_response(session, solved_count):
                if request.user.is_authenticated:
                    session.user = request.user
                
                session.completed_at = timezone.now()
                session.save()

                correct_total = session.answers.filter(is_correct=True).count()
                total_asked = session.answers.count()
                
                # Ищем самую первую ошибку (сортируем по времени создания)
                mistake_log = session.answers.filter(is_correct=False).order_by('created_at').first()
                mistake_info = None
                
                if mistake_log:
                    task = mistake_log.task
                    
                    # Вычисляем порядковый номер задачи (1, 2, 3...)
                    all_answers_ids = list(session.answers.order_by('created_at').values_list('id', flat=True))
                    task_number = all_answers_ids.index(mistake_log.id) + 1 if mistake_log.id in all_answers_ids else '?'

                    # Собираем все варианты ответов (картинки)
                    options = []
                    for i in range(1, 9):
                        option_field = getattr(task, f'option_{i}')
                        if option_field and hasattr(option_field, 'url'):
                            options.append({'id': f'option_{i}', 'url': option_field.url})
                            
                    # Приводим сырые ответы к формату 'option_X' для точного сравнения на фронте
                    u_raw = mistake_log.user_answer
                    u_raw = u_raw if u_raw.startswith('option_') else f'option_{u_raw}'
                    
                    c_raw = str(task.correct_answer)
                    c_raw = c_raw if c_raw.startswith('option_') else f'option_{c_raw}'

                    t_type_display = task.get_task_type_display() if hasattr(task, 'get_task_type_display') else task.task_type
                    
                    mistake_info = {
                        'task_number': task_number,
                        'task_type': t_type_display,
                        'main_image': task.image_content.url if task.image_content else '',
                        'options': options,
                        'user_answer': mistake_log.user_answer.replace('option_', 'Вариант '),
                        'correct_answer': str(task.correct_answer).replace('option_', 'Вариант '),
                        'user_answer_raw': u_raw,
                        'correct_answer_raw': c_raw
                    }
                    
                return JsonResponse({
                    'status': 'finished',
                    'correct_total': correct_total,
                    'total_asked': total_asked,
                    'is_registered': request.user.is_authenticated,
                    'mistake_info': mistake_info,
                    'session_id': str(session.id)
                })

            # === ЕСЛИ ТЕСТ ЗАВЕРШЕН (достигнут лимит) ===
            if solved_count >= TOTAL_QUESTIONS_LIMIT:
                return get_finished_response(session, solved_count)

            # Если тест продолжается
            available_tasks = Task.objects.filter(is_active=True).exclude(id__in=solved_task_ids)
            last_log = session.answers.order_by('-created_at').first()
            last_task_type = last_log.task.task_type if last_log else None
            
            from .services.calibration import find_next_best_task
            next_task = find_next_best_task(available_tasks, last_task_type)

            # === ЕСЛИ ЗАДАЧИ В БАЗЕ КОНЧИЛИСЬ РАНЬШЕ ЛИМИТА ===
            if not next_task:
                return get_finished_response(session, solved_count)

            options = []
            for i in range(1, 9):
                option_field = getattr(next_task, f'option_{i}')
                if option_field and hasattr(option_field, 'url'):
                    options.append({'id': f'option_{i}', 'url': option_field.url})
            
            fake_error = 2.0 - (solved_count / TOTAL_QUESTIONS_LIMIT) * 1.8

            return JsonResponse({
                'status': 'ok',
                'task': {
                    'id': next_task.id,
                    'type': next_task.task_type,
                    'text': next_task.text_content,
                    'main_image': next_task.image_content.url if next_task.image_content else '',
                    'options': options
                },
                'current_error': fake_error 
            })
            
        except TestSession.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Сессия не найдена'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

@csrf_exempt
def submit_answer(request):
    """Прием ответа без сложной математики IRT"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            session_id = data.get('session_id')
            task_id = data.get('task_id')
            user_answer = str(data.get('user_answer', '')).strip().lower() # Приходит 'option_2'
            time_spent = data.get('time_spent', 0)
            
            session = TestSession.objects.get(id=session_id)
            task = Task.objects.get(id=task_id)
            
            # Достаем то, что написано в базе (например, '2')
            correct_val = str(task.correct_answer).strip().lower()
            
            # УМНАЯ ПРОВЕРКА
            is_correct = (
                user_answer == correct_val or 
                user_answer == f"option_{correct_val}" or 
                f"option_{user_answer}" == correct_val
            )
            
            # Сохраняем результат лога
            AnswerLog.objects.create(
                session=session,
                task=task,
                user_answer=user_answer,
                is_correct=is_correct,
                time_spent_seconds=float(time_spent)
            )
            
            # МЫ БОЛЬШЕ НЕ ПЕРЕСЧИТЫВАЕМ ИНТЕЛЛЕКТ ЗДЕСЬ (калибровка)
            if request.user.is_authenticated:
                session.user = request.user
            session.save()
            
            return JsonResponse({'status': 'ok', 'is_correct': is_correct})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

        

# ... твои предыдущие функции для UI ...

def index(request):
    """Главная страница нашего IQ-теста"""
    return render(request, 'index.html')

def register_view(request):
    """Представление для регистрации нового пользователя"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Сразу логиним пользователя после регистрации
            return redirect('profile') # Отправляем в личный кабинет
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def profile_view(request):
    """Личный кабинет пользователя"""
    # Получаем все завершенные сессии текущего пользователя
    user_sessions = TestSession.objects.filter(user=request.user).exclude(estimated_ability__isnull=True).order_by('-id')
    
    return render(request, 'profile.html', {'sessions': user_sessions})