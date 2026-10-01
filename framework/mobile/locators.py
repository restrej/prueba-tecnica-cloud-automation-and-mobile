"""
Locators para elementos de una app Flutter.

¿Por qué Flutter es distinto a una app nativa?
    - Una app nativa Android crea vistas reales (TextView, Button) con ``resource-id``.
    - Flutter DIBUJA todo en un lienzo; Appium sólo ve el árbol de accesibilidad.
    - Por eso el desarrollador marca los widgets con ``Semantics(identifier: 'x')``
      (ver mobile-app/lib/main.dart), que Flutter publica como:
        * Android -> atributo ``resource-id``
        * iOS     -> ``accessibilityIdentifier`` (Appium lo busca como "accessibility id")
"""

import os

# AppiumBy: estrategias de búsqueda propias de Appium (además de las de Selenium).
from appium.webdriver.common.appiumby import AppiumBy

# Locator del campo de texto que tiene el foco en Android (donde "escribe" el teclado).
FOCUSED_INPUT_ANDROID = (AppiumBy.ANDROID_UIAUTOMATOR, "new UiSelector().focused(true)")


def flutter_id(identifier: str) -> tuple[str, str]:
    """
    Devuelve el locator (estrategia, valor) para un ``Semantics(identifier: ...)``.

    Args:
        identifier: el identificador definido en el código Flutter (ej. ``"login-button"``).

    Returns:
        Tupla compatible con ``driver.find_element(*locator)`` y con ``WebDriverWait``.
    """
    if os.getenv("MOBILE_PLATFORM", "android").lower() == "ios":
        # En iOS el identifier es el accessibilityIdentifier.
        return AppiumBy.ACCESSIBILITY_ID, identifier
    # En Android usamos UiSelector de UiAutomator: busca por resource-id EXACTO.
    return AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{identifier}")'


def by_text(text: str) -> tuple[str, str]:
    """
    Locator por texto visible (sólo como último recurso: el texto cambia con traducciones).

    Args:
        text: texto exacto visible en pantalla.
    """
    if os.getenv("MOBILE_PLATFORM", "android").lower() == "ios":
        return AppiumBy.IOS_PREDICATE, f'label == "{text}"'
    return AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{text}")'
