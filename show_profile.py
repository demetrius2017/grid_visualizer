import cProfile
import pstats
import io

def print_profile_results():
    # Загружаем результаты профилирования
    s = io.StringIO()
    ps = pstats.Stats('profile_results.prof', stream=s).sort_stats('cumulative')
    ps.print_stats(50)  # Выводим 50 самых ресурсоемких функций
    print(s.getvalue())

if __name__ == '__main__':
    print_profile_results()