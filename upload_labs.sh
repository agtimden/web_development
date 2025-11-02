#!/bin/bash

# Скрипт для загрузки лабораторных работ в GitHub

cd "/Users/timofejagibalov/Desktop/Веб-разработка/ЛР"

# Функция для копирования файлов проекта
copy_project() {
    SOURCE_DIR="$1"
    # Копируем только нужные файлы, исключая ve и другие большие директории
    find "$SOURCE_DIR" -type f \( -name "*.py" -o -name "*.html" -o -name "*.css" -o -name "*.txt" -o -name "*.jpg" -o -name "*.png" -o -name "*.jpeg" \) ! -path "*/ve/*" ! -path "*/.venv/*" ! -path "*/__pycache__/*" ! -path "*/instance/*.db" -exec cp --parents {} . \;
}

# Создаем ветки для каждой лабораторной работы
create_branch() {
    BRANCH_NAME="$1"
    SOURCE_PATH="$2"
    
    git checkout main
    git checkout -b "$BRANCH_NAME"
    
    # Очищаем предыдущие файлы (кроме .git, README.md, .gitignore и папок с лабами)
    find . -mindepth 1 -maxdepth 1 ! -name '.git' ! -name 'README.md' ! -name '.gitignore' ! -name '№*' ! -name 'экзамен' ! -name 'upload_labs.sh' -exec rm -rf {} +
    
    # Копируем файлы проекта
    if [ -d "$SOURCE_PATH/lab1_template" ]; then
        copy_project "$SOURCE_PATH/lab1_template"
    elif [ -d "$SOURCE_PATH" ]; then
        copy_project "$SOURCE_PATH"
    fi
    
    # Добавляем файлы
    git add app/ requirements.txt "команды.txt" 2>/dev/null || true
    git add -A 2>/dev/null || true
    
    # Коммитим
    git commit -m "Add $BRANCH_NAME project files" || true
}

# Создаем ветки
create_branch "lab1" "№ 1"
create_branch "lab2" "№ 2"
create_branch "lab3" "№ 3"
create_branch "lab4" "№ 4"
create_branch "lab5" "№ 5"
create_branch "lab6" "№ 6"
create_branch "exam" "экзамен"

# Возвращаемся на main
git checkout main

echo "Все ветки созданы!"

