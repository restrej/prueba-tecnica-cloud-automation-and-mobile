"""
Simulador del lector de código de barras para pruebas en emulador.

Problema: los operadores usan un scanner FÍSICO que no existe en un emulador.
Solución: casi todos los scanners industriales (Zebra, Honeywell) trabajan en modo
"keyboard wedge": se comportan como un TECLADO que escribe el código y presiona
ENTER. Entonces escanear = escribir el código + ENTER en el campo enfocado.

Estrategias implementadas:
    1. ``type``: escribe en el campo de escaneo vía Appium y envía ENTER.
       Funciona en Android e iOS, sin permisos especiales. (Por defecto)
    2. ``adb``:  inyecta las teclas a nivel de sistema operativo con ``adb shell input``,
       que es exactamente lo que hace un scanner wedge real. Requiere iniciar
       Appium con ``--allow-insecure=adb_shell`` (sólo Android).

Lo que NO se puede simular: la óptica real (códigos dañados, reflejos, distancia).
Eso queda para pruebas manuales en dispositivo físico (ver respuesta 2.2).
"""

# Tipo del driver de Appium (sólo para anotaciones).
from appium.webdriver.webdriver import WebDriver

# Código de tecla ENTER en Android (KEYCODE_ENTER = 66).
ANDROID_KEYCODE_ENTER = 66


class BarcodeScannerSimulator:
    """Simula lecturas del scanner sobre el campo de escaneo de PickApp."""

    def __init__(self, driver: WebDriver, strategy: str = "type") -> None:
        """
        Args:
            driver: sesión de Appium.
            strategy: ``"type"`` o ``"adb"`` (ver docstring del módulo).
        """
        self.driver = driver
        self.strategy = strategy

    def scan(self, scan_field, barcode: str) -> None:
        """
        Realiza una "lectura" del código.

        Args:
            scan_field: elemento del campo de escaneo (ya localizado por el Screen Object).
            barcode: código EAN/UPC a "leer".
        """
        if self.strategy == "adb":
            # Damos foco al campo y "tecleamos" a nivel de sistema operativo.
            scan_field.click()
            self.driver.execute_script("mobile: shell", {"command": "input", "args": ["text", barcode]})
            self.driver.execute_script("mobile: shell", {"command": "input", "args": ["keyevent", "66"]})
            return
        # Estrategia por defecto: escribir en el campo y presionar ENTER.
        scan_field.click()
        scan_field.clear()
        scan_field.send_keys(barcode)
        if self.driver.capabilities.get("platformName", "").lower() == "android":
            self.driver.press_keycode(ANDROID_KEYCODE_ENTER)
        else:
            # En iOS, "\n" equivale a presionar Return en el teclado.
            scan_field.send_keys("\n")
