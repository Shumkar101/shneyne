import os
import re
from django.core.management.base import BaseCommand
from django.core.files import File
from iq_test.models import Task, TaskType

class Command(BaseCommand):
    help = 'Массово загружает задачи из папок и текстового файла с ответами'

    def handle(self, *args, **kwargs):
        # 1. Укажи путь к твоей главной папке с задачами
        # Сейчас предполагается, что папка "import_data" лежит рядом с manage.py
        base_dir = os.path.join(os.getcwd(), 'import_data')
        answers_file = os.path.join(base_dir, 'answers.txt')

        if not os.path.exists(base_dir):
            self.stdout.write(self.style.ERROR(f'Папка не найдена: {base_dir}'))
            return

        if not os.path.exists(answers_file):
            self.stdout.write(self.style.ERROR(f'Файл с ответами не найден: {answers_file}'))
            return

        # 2. Читаем файл с ответами
        answers = []
        with open(answers_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if '=' in line:
                    # Берем всё, что после '=', и убираем пробелы в начале и конце
                    after_equals = line.split('=')[-1].strip()
                    # Разбиваем оставшийся текст по пробелам и берем только первое слово (цифру)
                    correct_ans = after_equals.split()[0]
                    answers.append(correct_ans)

        self.stdout.write(f'Найдено ответов в файле: {len(answers)}')

        # 3. Ищем все папки внутри главной папки и сортируем их по числам
        # Это нужно, чтобы папка "task_10" шла после "task_9", а не после "task_1"
        folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
        
        def extract_number(folder_name):
            numbers = re.findall(r'\d+', folder_name)
            return int(numbers[0]) if numbers else 0
            
        folders.sort(key=extract_number)
        
        self.stdout.write(f'Найдено папок с задачами: {len(folders)}')

        tasks_created = 0

        # 4. Проходимся по папкам и создаем задачи
        for idx, folder_name in enumerate(folders):
            if idx >= len(answers):
                self.stdout.write(self.style.WARNING(f'Для папки {folder_name} нет ответа в файле (строка {idx+1}). Пропуск.'))
                continue

            correct_ans = answers[idx]
            folder_path = os.path.join(base_dir, folder_name)

            # Создаем черновик задачи в базе
            task = Task(
                task_type=TaskType.BOOLEAN_LOGIC,  # Указываем новый тип
                text_content="",                     # Оставляем текст пустым
                correct_answer=correct_ans,
                estimated_weight=1.0,
                is_active=True
            )

            # Перебираем файлы в папке задачи
            files = os.listdir(folder_path)
            
            for filename in files:
                file_path = os.path.join(folder_path, filename)
                
                # Пропускаем, если это папка (на всякий случай)
                if not os.path.isfile(file_path):
                    continue

                # Ищем главную картинку (условие)
                name_lower = filename.lower()
                if 'main' in name_lower or 'matrix' in name_lower:
                    with open(file_path, 'rb') as img_f:
                        task.image_content.save(filename, File(img_f), save=False)
                else:
                    # Ищем картинки вариантов ответов (проверяем наличие цифр от 1 до 8)
                    match = re.search(r'(\d)', filename)
                    if match:
                        opt_num = int(match.group(1))
                        if 1 <= opt_num <= 8:
                            # Динамически получаем поле option_1, option_2 и т.д.
                            field = getattr(task, f'option_{opt_num}')
                            with open(file_path, 'rb') as img_f:
                                field.save(filename, File(img_f), save=False)

            # Сохраняем готовую задачу со всеми файлами в базу данных
            task.save()
            tasks_created += 1
            self.stdout.write(self.style.SUCCESS(f'Успешно загружена задача из папки: {folder_name} (Ответ: {correct_ans})'))

        self.stdout.write(self.style.SUCCESS(f'\nИтого загружено новых задач: {tasks_created}'))