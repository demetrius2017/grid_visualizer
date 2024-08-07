import glfw
from OpenGL.GL import *

# Инициализация GLFW
if not glfw.init():
    raise Exception("GLFW не удалось инициализировать")

# Создание окна
window = glfw.create_window(800, 600, "GLFW Window", None, None)
if not window:
    glfw.terminate()
    raise Exception("Не удалось создать окно GLFW")

glfw.make_context_current(window)

# Главный цикл
while not glfw.window_should_close(window):
    glClear(GL_COLOR_BUFFER_BIT)

    # Рендеринг (пример с треугольником)
    glBegin(GL_TRIANGLES)
    glVertex2f(-0.5, -0.5)
    glVertex2f( 0.5, -0.5)
    glVertex2f( 0.0,  0.5)
    glEnd()

    glfw.swap_buffers(window)
    glfw.poll_events()

glfw.terminate()
