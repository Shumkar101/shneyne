import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Task, TestSession, AnswerLog
from .services.irt import estimate_ability_and_error, find_next_best_task
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
def get_next_task(request):
    """Эндпоинт 2: Выдача следующей задачи с учетом Интеллекта"""
    if request.method == 'POST':
        data = json.loads(request.body)
        session_id = data.get('session_id')
        
        try:
            session = TestSession.objects.get(id=session_id)
            
            # УСЛОВИЕ ОСТАНОВКИ ТЕСТА:
            # 1. Если погрешность стала меньше 0.4 (мы точно знаем интеллект)
            # 2. ИЛИ человек решил уже 30 задач (чтобы тест не шел бесконечно)
            answers_count = session.answers.count()
            if session.standard_error < 0.4 or answers_count >= 30:
                # === НАЧАЛО БЛОКА ЗАВЕРШЕНИЯ ТЕСТА ===
        
                # 1. Сохраняем результат за пользователем (если он вошел)
                if request.user.is_authenticated:
                    session.user = request.user
                session.save()

                # 2. Собираем умную аналитику
                logs = AnswerLog.objects.filter(session=session).select_related('task')
                analytics = {}
                correct_total = 0
                
                for log in logs:
                    t_type = log.task.task_type 
                    if t_type not in analytics:
                        analytics[t_type] = {'correct': 0, 'total': 0}
                    
                    analytics[t_type]['total'] += 1
                    if log.is_correct:
                        analytics[t_type]['correct'] += 1
                        correct_total += 1
                        
                weakest_type = None
                lowest_pct = 1.0
                
                for t_type, stats in analytics.items():
                    pct = stats['correct'] / stats['total']
                    if pct < lowest_pct:
                        lowest_pct = pct
                        weakest_type = t_type
                        
                # 3. Формируем рекомендацию
                if weakest_type and lowest_pct <= 0.5:
                    rec = f"Твоя база хороша, но задачи типа «{weakest_type}» даются тяжело. Обрати внимание на логику этих паттернов, чтобы пробить потолок IQ!"
                elif correct_total == len(logs) and len(logs) > 0:
                    rec = "Потрясающий результат! У тебя железобетонная логика и абсолютно нет слабых мест."
                else:
                    rec = "Отличный, сбалансированный результат! Твоя логика работает стабильно по всем типам визуальных матриц."
                    
                # 4. Отдаем на фронтенд
                return JsonResponse({
                    'status': 'finished',
                    'final_score': int(session.estimated_ability * 15 + 100), 
                    'tasks_solved': correct_total,
                    'total_asked': len(logs),
                    'analytics': analytics,   
                    'recommendation': rec     
                })
                # === КОНЕЦ БЛОКА ЗАВЕРШЕНИЯ ТЕСТА ===

            # Если тест продолжается, ищем задачи, которые юзер еще не решал
            solved_task_ids = session.answers.values_list('task_id', flat=True)
            available_tasks = Task.objects.filter(is_active=True).exclude(id__in=solved_task_ids)
            
            if not available_tasks.exists():
                return JsonResponse({'status': 'finished', 'message': 'База задач исчерпана'})

            # МАГИЯ IRT: Ищем задачу, подходящую под текущий уровень пользователя
            next_task = find_next_best_task(session.estimated_ability, available_tasks)

            # Собираем данные задачи, чтобы отправить в браузер
            # Проверяем наличие картинок, чтобы не словить ошибку
            task_data = {
                'id': next_task.id,
                'type': next_task.task_type,
                'text': next_task.text_content,
                'main_image': next_task.image_content.url if next_task.image_content else None,
                'options': []
            }
            
            # Собираем все непустые картинки-варианты ответов
            for i in range(1, 9):
                option_field = getattr(next_task, f'option_{i}')
                if option_field:
                    task_data['options'].append({
                        'id': f'option_{i}',
                        'url': option_field.url
                    })

            return JsonResponse({'status': 'ok', 'task': task_data, 'current_error': session.standard_error})
            
        except TestSession.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Сессия не найдена'}, status=404)

@csrf_exempt
def submit_answer(request):
    """Прием ответа и пересчет Интеллекта с умной проверкой"""
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
            
            # УМНАЯ ПРОВЕРКА:
            # Ответ верен, если:
            # 1. Строки совпадают полностью ('option_2' == 'option_2')
            # 2. Или если в базе '2', а пришло 'option_2'
            # 3. Или если в базе 'option_2', а пришло просто '2'
            is_correct = (
                user_answer == correct_val or 
                user_answer == f"option_{correct_val}" or 
                f"option_{user_answer}" == correct_val
            )
            
            # Сохраняем результат
            AnswerLog.objects.create(
                session=session,
                task=task,
                user_answer=user_answer,
                is_correct=is_correct,
                time_spent_seconds=float(time_spent)
            )
            
            # Пересчет способностей (IRT)
            all_logs = session.answers.select_related('task').all()
            responses_for_irt = [
                {'b': log.task.estimated_weight, 'is_correct': log.is_correct} 
                for log in all_logs
            ]
            
            from .services.irt import estimate_ability_and_error
            new_theta, new_error = estimate_ability_and_error(responses_for_irt)
            
            session.estimated_ability = new_theta
            session.standard_error = new_error
            if request.user.is_authenticated:
                session.user = request.user
            session.save()
            
            return JsonResponse({'status': 'ok', 'is_correct': is_correct})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)

        

# ... твои предыдущие функции API ...

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
    # (предполагается, что у тебя в TestSession сохраняется estimated_ability)
    user_sessions = TestSession.objects.filter(user=request.user).exclude(estimated_ability__isnull=True).order_by('-id')
    
    return render(request, 'profile.html', {'sessions': user_sessions})