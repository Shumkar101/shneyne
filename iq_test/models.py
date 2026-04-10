import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class TaskType(models.TextChoices):
    """Категории задач для балансировки теста"""
    MATRIX = 'Lines', 'Линии'
    HALF_LINES = 'Half lines', 'половины линий'
    CROSING_LINES = 'crosing lines', 'пересекающиеся линии'
    ROTATING_SHAPES = 'rotating shapes', 'вращающиеся фигуры'
    SPLIT_VERTICAL_GRID = 'split vertical grid', 'разделенная вертикальная сетка'
    RADIAL_LINES = 'radial lines', 'радиальные линии'
    UMNOJENIE_DROBEI = 'umnojenie drobei', 'умножение дробей'
    INTERACTIONS_FIGURES = 'interactions figures', 'взаимодействия фигур'
    CIRCLES_AND_DOTS = 'circles and dots', 'круги и точки'
    GRID_3X3 = '3x3 grid', '3х3 сетка'
    LOGICAL_SWAP = 'logical swap', 'логический обмен'
    CUBES_REFLECTIONS = 'cubes reflections', 'кубы и отражения'
    ROTATING_DOT_HEXAGON = 'rotating dot hexagon', 'вращающаяся точка в шестиугольнике'
    LINE_XOR_LOGIC = 'line XOR logic', 'логика ИЛИ для линий'
    POLYGON_SIDES_TOGGLE = 'polygon sides toggle', 'переключение сторон многоугольника'
    CLOCK_HANDS_ROTATION = 'clock hands rotation', 'вращение стрелок часов'
    DOT_SET_UNION = 'Dot Set Union', 'Объединение множеств точек'
    SQUARE_LINE_A = 'Square Line Logic A', 'Логика квадратных линий A'
    SQUARE_LINE_B = 'Square Line Logic B', 'Логика квадратных линий B'
    SQUARE_LINE_C = 'Square Line Logic C', 'Логика квадратных линий C'
    SQUARE_LINE_D = 'Square Line Logic D', 'Логика квадратных линий D'
    SQUARE_LINE_E = 'Square Line Logic E', 'Логика квадратных линий E'
    FILL_SQUARE = 'Fill Square', 'Заполнение квадрата'
    DISTRIBUTED_FIGURES = 'distributed figures', 'распределенные фигуры'
    BOOLEAN_LOGIC = '02 Boolean Logic', 'Логика Булевых значений'
    PATTERN_ROTATION = 'pattern rotation', 'Вращение образцов'
    ARITHMETIC_COUNT = 'arithmetic count', 'Арифметический подсчет'
    GRAVITY_INVERSION = 'gravity inversion', 'Инверсия гравитации'
    OTHER = 'other', 'Другое'


class Sphere(models.TextChoices):
    """Сфера деятельности пользователя"""
    TECH = 'tech', 'Техническая / IT'
    HUMANITIES = 'humanities', 'Гуманитарная'
    NATURAL_SCIENCES = 'natural', 'Естественные науки'
    STUDENT = 'student', 'Учащийся / Студент'
    OTHER = 'other', 'Другое'

class Task(models.Model):
    """Модель задачи с поддержкой 9 картинок"""
    task_type = models.CharField(max_length=20, choices=TaskType.choices, verbose_name="Тип задачи")
    text_content = models.TextField(blank=True, null=True, verbose_name="Текст задачи")
    
    # Заменили ImageField на FileField для поддержки SVG
    image_content = models.FileField(upload_to='tasks/main/', blank=True, null=True, verbose_name="Главное изображение (условие)")
    
    # 8 вариантов ответов (отдельные картинки)
    option_1 = models.FileField(upload_to='tasks/options/', blank=True, null=True, verbose_name="Вариант 1")
    option_2 = models.FileField(upload_to='tasks/options/', blank=True, null=True, verbose_name="Вариант 2")
    option_3 = models.FileField(upload_to='tasks/options/', blank=True, null=True, verbose_name="Вариант 3")
    option_4 = models.FileField(upload_to='tasks/options/', blank=True, null=True, verbose_name="Вариант 4")
    option_5 = models.FileField(upload_to='tasks/options/', blank=True, null=True, verbose_name="Вариант 5")
    option_6 = models.FileField(upload_to='tasks/options/', blank=True, null=True, verbose_name="Вариант 6")
    option_7 = models.FileField(upload_to='tasks/options/', blank=True, null=True, verbose_name="Вариант 7")
    option_8 = models.FileField(upload_to='tasks/options/', blank=True, null=True, verbose_name="Вариант 8")
    
    # Правильный ответ (например, 'option_4')
    correct_answer = models.CharField(max_length=255, verbose_name="Правильный ответ")
    
    estimated_weight = models.FloatField(default=1.0, verbose_name="Предполагаемый вес сложности")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"

    def __str__(self):
        return f"Задача #{self.id} [{self.get_task_type_display()}]"


class TestSession(models.Model):
    """Сессия прохождения теста"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='test_sessions')
    age = models.PositiveIntegerField(null=True, blank=True, verbose_name="Возраст")
    sphere = models.CharField(max_length=20, choices=Sphere.choices, null=True, blank=True, verbose_name="Сфера деятельности")
    started_at = models.DateTimeField(default=timezone.now, verbose_name="Начало теста")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Окончание теста")

    # НОВЫЕ ПОЛЯ ДЛЯ АДАПТИВНОГО ТЕСТА:
    estimated_ability = models.FloatField(default=0.0, verbose_name="Оценка способности (θ)")
    standard_error = models.FloatField(default=3.0, verbose_name="Текущая погрешность")

    class Meta:
        verbose_name = "Сессия тестирования"
        verbose_name_plural = "Сессии тестирования"

    def __str__(self):
        return f"Сессия {self.id} (Возраст: {self.age})"


class AnswerLog(models.Model):
    """Лог ответа на конкретную задачу"""
    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='answers', verbose_name="Сессия")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='answers', verbose_name="Задача")
    user_answer = models.CharField(max_length=255, verbose_name="Ответ пользователя")
    is_correct = models.BooleanField(default=False, verbose_name="Верно")
    time_spent_seconds = models.FloatField(verbose_name="Затраченное время (сек)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Лог ответа"
        verbose_name_plural = "Логи ответов"
        unique_together = ('session', 'task')

    def __str__(self):
        return f"Ответ {self.user_answer} ({'Верно' if self.is_correct else 'Неверно'}) на Задачу #{self.task.id}"