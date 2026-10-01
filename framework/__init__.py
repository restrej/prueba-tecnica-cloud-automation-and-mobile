"""
Paquete ``framework``: código REUTILIZABLE por todas las pruebas.

Separar "cómo se habla con el sistema" (framework) de "qué se prueba" (tests)
es la base de un framework mantenible:
    - ``framework/api``    -> cliente de la API (patrón API Object / Service Object).
    - ``framework/ui``     -> Page Objects de la web (patrón Page Object Model).
    - ``framework/mobile`` -> Screen Objects de la app móvil + utilidades Appium.
Si mañana cambia un endpoint o un botón, se corrige en UN solo lugar.
"""
