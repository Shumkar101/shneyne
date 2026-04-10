import math

# Ограничители, чтобы математика не сломалась от бесконечностей
MAX_THETA = 4.0
MIN_THETA = -4.0

def calculate_probability(theta, b):
    """
    Формула 1PL (Раша). 
    Вычисляет вероятность правильного ответа пользователя с интеллектом `theta` 
    на задачу со сложностью `b`.
    """
    # Защита от переполнения math.exp
    x = theta - b
    if x > 20: return 0.9999
    if x < -20: return 0.0001
    
    return 1.0 / (1.0 + math.exp(-x))

def calculate_item_information(theta, b):
    """
    Информация Фишера для одной задачи.
    Показывает, насколько эта задача полезна для измерения именно этого уровня theta.
    Максимум информации достигается, когда сложность задачи равна уровню пользователя (theta == b).
    """
    p = calculate_probability(theta, b)
    return p * (1.0 - p)

def estimate_ability_and_error(responses):
    """
    Вычисляет текущий уровень интеллекта (theta) и погрешность (Standard Error)
    на основе всех ответов в текущей сессии.
    
    responses - список словарей вида: [{'b': 1.2, 'is_correct': True}, {'b': -0.5, 'is_correct': False}]
    """
    if not responses:
        return 0.0, 3.0 # Базовые значения для начала теста
        
    correct_answers = sum(1 for r in responses if r['is_correct'])
    
    # Краевые случаи: если человек ответил на ВСЕ правильно или на ВСЕ неправильно,
    # метод правдоподобия улетит в бесконечность. Делаем грубый сдвиг.
    if correct_answers == len(responses):
        current_theta = responses[-1]['b'] + 1.0 # Увеличиваем на шаг
        # Информацию посчитать нельзя корректно, ставим искусственную высокую погрешность
        return min(current_theta, MAX_THETA), 2.0 
        
    if correct_answers == 0:
        current_theta = responses[-1]['b'] - 1.0 # Уменьшаем на шаг
        return max(current_theta, MIN_THETA), 2.0

    # Метод Максимального Правдоподобия (Ньютона-Рафсона)
    # Ищем такую theta, при которой производная функции правдоподобия равна 0
    theta = 0.0 # Стартовая точка
    
    for _ in range(10): # Обычно сходится за 4-5 итераций
        expected_score = 0.0
        test_information = 0.0
        
        for r in responses:
            p = calculate_probability(theta, r['b'])
            expected_score += p
            test_information += calculate_item_information(theta, r['b'])
            
        # Сдвиг Ньютона-Рафсона
        difference = correct_answers - expected_score
        
        # Защита от деления на ноль
        if test_information < 0.001: 
            break
            
        delta = difference / test_information
        theta += delta
        
        # Если сдвиг микроскопический, значит мы нашли точное значение
        if abs(delta) < 0.001:
            break
            
    # Обрезаем экстремальные значения
    theta = max(MIN_THETA, min(MAX_THETA, theta))
    
    # Считаем итоговую погрешность (Standard Error of Measurement)
    # SE = 1 / sqrt(Test Information)
    final_information = sum(calculate_item_information(theta, r['b']) for r in responses)
    standard_error = 1.0 / math.sqrt(final_information) if final_information > 0 else 3.0
    
    return theta, standard_error

def find_next_best_task(current_theta, available_tasks):
    """
    Ищет в базе задачу, сложность которой ближе всего к текущему интеллекту пользователя.
    available_tasks - QuerySet из Django БД (задачи, которые юзер еще не решал)
    """
    best_task = None
    min_diff = float('inf')
    
    for task in available_tasks:
        diff = abs(task.estimated_weight - current_theta)
        if diff < min_diff:
            min_diff = diff
            best_task = task
            
    return best_task