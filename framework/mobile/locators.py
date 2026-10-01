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

# Locator de la CAJA DE TEXTO editable (EditText) que tiene el foco en Android.
FOCUSED_INPUT_ANDROID = (
    AppiumBy.ANDROID_UIAUTOMATOR,
    'new UiSelector().className("android.widget.EditText").focused(true)',
)


def editable_child_android(identifier: str) -> tuple[str, str]:
    """Caja de texto (EditText) que está DENTRO del elemento con ese identificador de Flutter."""
    return (
        AppiumBy.ANDROID_UIAUTOMATOR,
        f'new UiSelector().resourceId("{identifier}")'
        '.childSelector(new UiSelector().className("android.widget.EditText"))',
    )


def scroll_into_view_android(identifier: str) -> tuple[str, str]:
    """Locator que, al buscarlo, DESPLAZA la lista hasta que el elemento sea visible (UiScrollable)."""
    return (
        AppiumBy.ANDROID_UIAUTOMATOR,
        "new UiScrollable(new UiSelector().scrollable(true))"
        f'.scrollIntoView(new UiSelector().resourceId("{identifier}"))',
    )


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
