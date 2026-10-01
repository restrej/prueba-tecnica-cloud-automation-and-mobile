"""
Capabilities de Appium: la "ficha" que le dice a Appium qué sesión abrir.

Todo sale de variables de entorno para poder correr la MISMA prueba en
distintos dispositivos/resoluciones cambiando sólo el entorno (matriz en CI):

    ANDROID_DEVICE_NAME=Pixel_7_API_34 APP_PATH=/ruta/app-debug.apk pytest -m mobile
"""

# os: leer variables de entorno; Path: validar/normalizar la ruta del APK.
import os
from pathlib import Path

# UiAutomator2Options: capabilities tipadas para Android (driver UiAutomator2).
from appium.options.android import UiAutomator2Options

# XCUITestOptions: capabilities tipadas para iOS (driver XCUITest).
from appium.options.ios import XCUITestOptions

# APK por defecto: el que genera `flutter build apk --debug` dentro de mobile-app/.
DEFAULT_APK = Path(__file__).resolve().parents[2] / "mobile-app/build/app/outputs/flutter-apk/app-debug.apk"


def android_options() -> UiAutomator2Options:
    """
    Construye las capabilities para Android.

    Returns:
        Objeto de opciones listo para ``webdriver.Remote(..., options=...)``.
    """
    options = UiAutomator2Options()
    # Plataforma y motor de automatización (UiAutomator2 = el estándar de Android).
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    # Nombre del dispositivo/emulador (informativo en Android; "adb devices" lo resuelve).
    options.device_name = os.getenv("ANDROID_DEVICE_NAME", "Android Emulator")
    # Versión de Android (opcional): permite elegir un emulador concreto en granjas de dispositivos.
    if os.getenv("ANDROID_PLATFORM_VERSION"):
        options.platform_version = os.environ["ANDROID_PLATFORM_VERSION"]
    # Si hay varios dispositivos conectados, "udid" elige uno (ej. emulator-5554).
    if os.getenv("ANDROID_UDID"):
        options.udid = os.environ["ANDROID_UDID"]
    # Ruta del APK a instalar.
    options.app = os.getenv("APP_PATH", str(DEFAULT_APK))
    # Paquete de la app (definido en `flutter create --org com.logitrack`).
    options.app_package = "com.logitrack.pickapp"
    options.app_activity = ".MainActivity"
    # Concede permisos (cámara, almacenamiento) automáticamente: evita popups que rompen la prueba.
    options.auto_grant_permissions = True
    # no_reset=False: cada sesión arranca con la app limpia (datos de la sesión anterior borrados).
    options.no_reset = False
    # Tiempo (s) que Appium espera un comando nuevo antes de cerrar la sesión.
    options.new_command_timeout = 120
    # Desactiva animaciones del sistema: menos flakiness por elementos "en movimiento".
    options.set_capability("appium:disableWindowAnimation", True)
    return options


def ios_options() -> XCUITestOptions:
    """
    Capabilities equivalentes para iOS (simulador). Requiere macOS + Xcode.

    Returns:
        Objeto de opciones para XCUITest.
    """
    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.automation_name = "XCUITest"
    options.device_name = os.getenv("IOS_DEVICE_NAME", "iPhone 15")
    options.platform_version = os.getenv("IOS_PLATFORM_VERSION", "17.5")
    # .app compilado para simulador con `flutter build ios --simulator`.
    options.app = os.getenv("APP_PATH", "mobile-app/build/ios/iphonesimulator/Runner.app")
    options.bundle_id = "com.logitrack.pickapp"
    options.new_command_timeout = 120
    return options


def build_options():
    """
    Elige las capabilities según ``MOBILE_PLATFORM`` (android | ios).

    Returns:
        Opciones de Android (por defecto) o de iOS.
    """
    return ios_options() if os.getenv("MOBILE_PLATFORM", "android").lower() == "ios" else android_options()
