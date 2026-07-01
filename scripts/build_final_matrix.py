import pandas as pd
import numpy as np
import os

if __name__ == "__main__":
    print("[МАСТЕР-СКРИПТ] Обработка вакансий и запуск динамической математики таргета...")
    
    # ЧТЕНИЕ ДАННЫХ ИЗ АБСОЛЮТНОГО ПУТИ INTERIM
    input_file = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\interim\data_interim_vacancies.csv"
    if not os.path.exists(input_file):
        print(f"[ОШИБКА] Файл {input_file} не найден! Сначала запустите parse_html_vacancies.py.")
        exit(1)
        
    df = pd.read_csv(input_file)
    
    # МАТЕМАТИКА ВОССТАНОВЛЕНИЯ ТАРГЕТА (TARGET RECOVERY)
    # Приведение типов и заполнение базовых пустот
    df['salary_from'] = df['salary_from'].fillna(0).astype(float)
    df['salary_to'] = df['salary_to'].fillna(0).astype(float)
    
    # Достраиваем односторонние вилки по рыночному коэффициенту 1.35
    df.loc[(df['salary_from'] > 0) & (df['salary_to'] == 0), 'salary_to'] = df['salary_from'] * 1.35
    df.loc[(df['salary_to'] > 0) & (df['salary_from'] == 0), 'salary_from'] = df['salary_to'] / 1.35
    
    # Маска стажеров (вакансии без опыта)
    is_intern = (df['experience_months'] == 0)
    
    # Динамический расчет y_offer на основе требований к hard/soft навыкам работодателя
    df['y_offer'] = (df['salary_from'] + df['salary_to']) / 2.0
    df.loc[is_intern, 'y_offer'] = df['salary_from']
    df.loc[(df['skills_completion_rate'] <= 0.20) & (~is_intern), 'y_offer'] = df['salary_from']
    df.loc[(df['skills_completion_rate'] > 0.60) & (~is_intern), 'y_offer'] = df['salary_to']
    
    # ФИНАЛЬНАЯ ОЧИСТКА И ПОКЛАССОВЫЙ АУДИТ IQR
    initial_size = len(df)
    clean_list = []
    
    for role_id in df['role_class'].unique():
        sub = df[df['role_class'] == role_id].copy()
        # Если вакансий по редкой роли мало, оставляем как есть для сохранения объема данных
        if len(sub) < 5:
            clean_list.append(sub)
            continue
        q25, q75 = sub['y_offer'].quantile(0.25), sub['y_offer'].quantile(0.75)
        iqr = q75 - q25
        # Фильтруем выбросы (слишком маленькие или аномально огромные зарплаты внутри конкретной банковской роли)
        clean_sub = sub[(sub['y_offer'] >= max(0, q25 - 1.5*iqr)) & (sub['y_offer'] <= q75 + 1.5*iqr)]
        clean_list.append(clean_sub)
        
    df_final = pd.concat(clean_list, ignore_index=True)
    df_final['region_tier'] = df_final['region_tier'].astype('category')
    
    final_size = len(df_final)
    print("\n" + "="*50)
    print(f"Удалено аномальных выбросов по IQR внутри ролей: {initial_size - final_size} строк.")
    print(f"ФИНАЛЬНЫЙ ОБЪЕМ МАТРИЦЫ ВАКАНСИЙ ДЛЯ ML: {final_size} строк.")
    
    # ПРОМЫШЛЕННЫЙ КОМПЛАЕНС-КОНТРОЛЬ ПОРОГА (БЕЗ ПАДЕНИЯ)
    if final_size < 3400:
        print("\n [ВНИМАНИЕ / COMPLIANCE WARNING]")
        print(f"    Текущий объем чистой матрицы вакансий ({final_size} стр.) ниже промышленного порога в 3400 строк!")
        print("    Для XGBoost/CatBoost моделей на этапе MVP этого может хватить, однако")
        print("    перед финальной защитой рекомендуется дозапустить Selenium-парсер")
        print("    по дополнительным городам или смежным ключевым словам для расширения выборки.")
    else:
        print("\n [ОК] Условия комплаенса полностью выполнены.")
        print(f"    Объем данных ({final_size} стр.) достаточен для стабильного обучения моделей.")
    print("="*50)

    # 5. СОХРАНЕНИЕ В ПРОМЫШЛЕННЫЙ BINARY PARQUET ФОРМАТ
    output_dir = r"C:\Users\Asus\OneDrive\Рабочий стол\Project ML ITMO\Модуль №3 ML System Design and MFDP\MFDP\data\processed"
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "bank_salaries_matrix_final.parquet")
    df_final.to_parquet(output_file, index=False)
    print(f"\n[ВЫПОЛНЕНО] Итоговый файл успешно сохранен в '{output_file}'")