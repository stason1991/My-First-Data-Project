import pandas as pd
import numpy as np
import os

if __name__ == "__main__":
    print("[МАСТЕР-СКРИПТ] Слияние данных и запуск динамической математики таргета...")
    
    # 1. Читаем локальные спарсенные файлы
    df_vac = pd.read_csv("data_interim_vacancies.csv")
    df_res = pd.read_csv("data_interim_resumes.csv")
    
    # Объединяем в общую матрицу
    df = pd.concat([df_vac, df_res], ignore_index=True, sort=False)
    
    # Заполняем пропуски в специфичных для резюме колонках
    for col in ["edu_level_encoded", "has_car_and_driver_license"]:
        df[col] = df[col].fillna(0).astype(int)
        
    # 2. МАТЕМАТИКА ВОССТАНОВЛЕНИЯ ТАРГЕТА (из Шага 3)
    # Очищаем вилки вакансий
    df['salary_from'] = df['salary_from'].fillna(0).astype(float)
    df['salary_to'] = df['salary_to'].fillna(0).astype(float)
    
    # Достраиваем односторонние вилки по рыночному коэффициенту 1.35
    df.loc[(df['salary_from'] > 0) & (df['salary_to'] == 0), 'salary_to'] = df['salary_from'] * 1.35
    df.loc[(df['salary_to'] > 0) & (df['salary_from'] == 0), 'salary_from'] = df['salary_to'] / 1.35
    
    # Маска стажеров
    is_intern = (df['experience_months'] == 0)
    
    # Динамический расчет y_offer на основе плотности софт/хард навыков
    df['y_offer'] = (df['salary_from'] + df['salary_to']) / 2.0
    df.loc[is_intern, 'y_offer'] = df['salary_from']
    df.loc[(df['skills_completion_rate'] <= 0.20) & (~is_intern), 'y_offer'] = df['salary_from']
    df.loc[(df['skills_completion_rate'] > 0.60) & (~is_intern), 'y_offer'] = df['salary_to']
    
    # Для резюме, где изначально не было вилки, заполняем y_offer средним по его роли и региону
    # Это позволяет использовать резюме соискателей для обучения (Target Recovery для соискателей)
    df['y_offer'] = df['y_offer'].replace(0, np.nan)
    df['y_offer'] = df.groupby(['role_class', 'region_tier'])['y_offer'].transform(lambda x: x.fillna(x.mean()))
    # Если роль редкая, заполняем средним по роли глобально
    df['y_offer'] = df.groupby('role_class')['y_offer'].transform(lambda x: x.fillna(x.mean()))
    df['y_offer'] = df['y_offer'].fillna(60000).round(0).astype(int) # Финал дефолт, если данных совсем нет
    
    # 3. ФИНАЛЬНАЯ ОЧИСТКА И ПОКЛАССОВЫЙ АУДИТ IQR (из Шага 4)
    initial_size = len(df)
    clean_list = []
    
    for role_id in df['role_class'].unique():
        sub = df[df['role_class'] == role_id].copy()
        if len(sub) < 10:
            clean_list.append(sub)
            continue
        q25, q75 = sub['y_offer'].quantile(0.25), sub['y_offer'].quantile(0.75)
        iqr = q75 - q25
        # Фильтруем выбросы строго внутри конкретной банковской роли
        clean_sub = sub[(sub['y_offer'] >= max(0, q25 - 1.5*iqr)) & (sub['y_offer'] <= q75 + 1.5*iqr)]
        clean_list.append(clean_sub)
        
    df_final = pd.concat(clean_list, ignore_index=True)
    df_final['region_tier'] = df_final['region_tier'].astype('category')
    
    final_size = len(df_final)
    print("\n" + "="*50)
    print(f"Удалено аномальных выбросов по IQR внутри ролей: {initial_size - final_size} строк.")
    print(f"ФИНАЛЬНЫЙ ОБЪЕМ СЛИТОЙ ОФФЛАЙН МАТРИЦЫ: {final_size} строк.")
    
    # Наш жесткий Kill Switch комплаенса ИТМО
    if final_size < 3000:
        print(f"[КРИТИЧЕСКИЙ СТОП] Слитая база ({final_size} стр.) меньше 3000 строк! XGBoost пилот остановлен.")
        print("Рекомендация: запустите Selenium-скрипты сбора еще раз по другим городам или смежным ключевым словам.")
    else:
        print("[ОК] Условия комплаенса выполнены. Объем достаточен для обучения моделей.")
    print("="*50)
    
    os.makedirs("data/processed", exist_ok=True)
    df_final.to_parquet("data/processed/bank_salaries_matrix_final.parquet", index=False)
    print("[ВЫПОЛНЕНО] Итоговый файл сохранен в 'data/processed/bank_salaries_matrix_final.parquet'")