#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import shutil
import os
import sys

def copy_project_files(source_dir, dest_dir='.'):
    """Копирует файлы проекта, исключая ve, __pycache__, .db файлы"""
    if not os.path.exists(source_dir):
        print(f"Source directory {source_dir} does not exist")
        return
    
    for root, dirs, files in os.walk(source_dir):
        # Исключаем ненужные директории
        dirs[:] = [d for d in dirs if d not in ['ve', '__pycache__', '.venv', '.git']]
        
        # Вычисляем относительный путь
        rel_path = os.path.relpath(root, source_dir)
        if rel_path == '.':
            target_dir = dest_dir
        else:
            target_dir = os.path.join(dest_dir, rel_path)
        
        # Создаем целевую директорию
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        # Копируем файлы (исключая .db файлы)
        for file in files:
            if file.endswith('.db'):
                continue
            source_file = os.path.join(root, file)
            target_file = os.path.join(target_dir, file)
            try:
                shutil.copy2(source_file, target_file)
                print(f"Copied: {target_file}")
            except Exception as e:
                print(f"Error copying {source_file}: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python copy_files.py <source_dir> [dest_dir]")
        sys.exit(1)
    
    source = sys.argv[1]
    dest = sys.argv[2] if len(sys.argv) > 2 else '.'
    copy_project_files(source, dest)

